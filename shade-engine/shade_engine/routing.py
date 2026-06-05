"""그늘 가중 라우팅 (Phase 2).

Valhalla 커스텀 코스팅의 핵심 원리를 격자 그래프 + 다익스트라로 구현한다.
엣지 비용 = 거리 × (1 + α · 햇빛비율). α 를 키우면 '가장 그늘진 길', 0 이면 '최단'.
실제 운영에서는 OSM 도로 그래프 + Valhalla 로 대체하되, 가중치 공식은 동일하다.

여기서는 좁은 권역(출발~도착 bbox)에서 8방향 격자를 만들고, 각 노드의 햇빛 여부를
태양 1회 계산(좁은 영역이라 거의 일정)으로 구한 뒤 경로를 탐색한다.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass

from .buildings import Building
from .geo import LocalProjection, haversine_m
from .raycast import ProjectedBuilding, is_point_shaded

_MAX_SHADOW_DISTANCE_CAP_M = 1500.0


@dataclass(frozen=True)
class RouteOption:
    """라우팅 결과 하나."""

    name: str  # 'shortest' | 'balanced' | 'shadiest'
    alpha: float
    coords: list[tuple[float, float]]  # [(lat, lon), ...]
    distance_m: float
    sun_fraction: float  # 경로 노드 중 햇빛 비율 0~1

    @property
    def shade_percent(self) -> float:
        return round((1.0 - self.sun_fraction) * 100.0, 1)


def _project_buildings(buildings: list[Building], proj: LocalProjection) -> list[ProjectedBuilding]:
    out: list[ProjectedBuilding] = []
    for b in buildings:
        ring_xy = tuple(proj.to_xy(lat, lon) for lat, lon in b.ring)
        if len(ring_xy) >= 3:
            out.append(
                ProjectedBuilding(
                    ring_xy=ring_xy,
                    height_m=b.height_m,
                    height_estimated=b.height_estimated,
                    osm_id=b.osm_id,
                )
            )
    return out


def plan_routes(
    origin: tuple[float, float],
    dest: tuple[float, float],
    buildings: list[Building],
    sun_azimuth_deg: float,
    sun_altitude_deg: float,
    *,
    grid_spacing_m: float = 20.0,
    margin_m: float = 150.0,
    max_nodes: int = 6000,
    alphas: dict[str, float] | None = None,
    prefer_sun: bool = False,
) -> list[RouteOption]:
    """origin→dest 의 최단/균형/그늘(또는 햇빛) 경로 후보를 만든다.

    grid_spacing_m 간격의 8방향 격자에서 알파별 다익스트라를 돌린다. 격자가 너무
    커지면(max_nodes 초과) 간격을 자동으로 키워 노드 수를 제한한다. prefer_sun=True
    (겨울 모드)면 그늘 대신 햇빛을 최대화한다.
    """
    if alphas is None:
        third = "sunniest" if prefer_sun else "shadiest"
        alphas = {"shortest": 0.0, "balanced": 3.0, third: 12.0}

    (lat0, lon0), (lat1, lon1) = origin, dest
    min_lat, max_lat = sorted((lat0, lat1))
    min_lon, max_lon = sorted((lon0, lon1))

    proj = LocalProjection(lat0=(min_lat + max_lat) / 2, lon0=(min_lon + max_lon) / 2)
    ox, oy = proj.to_xy(*origin)
    dx, dy = proj.to_xy(*dest)
    x_lo, x_hi = sorted((ox, dx))
    y_lo, y_hi = sorted((oy, dy))
    x_lo -= margin_m
    x_hi += margin_m
    y_lo -= margin_m
    y_hi += margin_m

    # 노드 수 제한을 위해 필요 시 간격 자동 확대
    spacing = grid_spacing_m
    while ((x_hi - x_lo) / spacing + 1) * ((y_hi - y_lo) / spacing + 1) > max_nodes:
        spacing *= 1.5

    ncols = int((x_hi - x_lo) / spacing) + 1
    nrows = int((y_hi - y_lo) / spacing) + 1

    def node_xy(r: int, c: int) -> tuple[float, float]:
        return (x_lo + c * spacing, y_lo + r * spacing)

    def snap(x: float, y: float) -> tuple[int, int]:
        c = min(ncols - 1, max(0, round((x - x_lo) / spacing)))
        r = min(nrows - 1, max(0, round((y - y_lo) / spacing)))
        return (r, c)

    projected = _project_buildings(buildings, proj)
    tallest = max((b.height_m for b in projected), default=0.0)
    tan_alt = math.tan(math.radians(max(sun_altitude_deg, 0.0)))
    max_dist = (
        min(_MAX_SHADOW_DISTANCE_CAP_M, tallest / tan_alt) if tan_alt > 1e-6 else _MAX_SHADOW_DISTANCE_CAP_M
    )

    # 각 노드의 햇빛 여부 + 통행 가능 여부를 1회 계산(좁은 영역이라 태양 위치는 거의 일정).
    # 건물 내부 노드는 통행 불가(blocked) — 그렇지 않으면 '값싼 그늘'로 오인되어
    # 경로가 건물을 관통할 수 있다.
    sunny = [[False] * ncols for _ in range(nrows)]
    blocked = [[False] * ncols for _ in range(nrows)]
    for r in range(nrows):
        for c in range(ncols):
            res = is_point_shaded(
                node_xy(r, c),
                sun_azimuth_deg,
                sun_altitude_deg,
                projected,
                max_distance_m=max(max_dist, spacing),
            )
            sunny[r][c] = not res.shaded
            blocked[r][c] = res.reason == "inside_building"

    start = snap(ox, oy)
    goal = snap(dx, dy)
    # 출발/도착이 건물 내부로 스냅되어도 경로가 성립하도록 통행 허용
    blocked[start[0]][start[1]] = False
    blocked[goal[0]][goal[1]] = False

    # 회피 대상: 여름은 햇빛, 겨울(prefer_sun)은 그늘
    avoid = (
        [[not sunny[r][c] for c in range(ncols)] for r in range(nrows)] if prefer_sun else sunny
    )

    options: list[RouteOption] = []
    for name, alpha in alphas.items():
        path_nodes = _dijkstra(start, goal, nrows, ncols, spacing, avoid, blocked, alpha)
        coords = [proj.to_latlon(*node_xy(r, c)) for r, c in path_nodes]
        # 정확한 출발/도착 좌표로 끝점 치환(격자 스냅 오차 보정)
        if coords:
            coords[0] = origin
            coords[-1] = dest
        dist = sum(
            haversine_m(coords[i][0], coords[i][1], coords[i + 1][0], coords[i + 1][1])
            for i in range(len(coords) - 1)
        )
        sun_nodes = sum(1 for r, c in path_nodes if sunny[r][c])
        sun_frac = sun_nodes / len(path_nodes) if path_nodes else 0.0
        options.append(
            RouteOption(name=name, alpha=alpha, coords=coords, distance_m=dist, sun_fraction=sun_frac)
        )
    return options


# 8방향 이웃 (dr, dc)
_NEIGHBORS = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]


def _dijkstra(
    start: tuple[int, int],
    goal: tuple[int, int],
    nrows: int,
    ncols: int,
    spacing: float,
    avoid: list[list[bool]],
    blocked: list[list[bool]],
    alpha: float,
) -> list[tuple[int, int]]:
    """엣지비용 = 거리 × (1 + α · 엣지회피비율) 다익스트라. 경로 노드열 반환.

    avoid 는 회피 대상(여름=햇빛, 겨울=그늘) 노드. blocked 노드(건물 내부)는 통행 불가.
    """
    def idx(r: int, c: int) -> int:
        return r * ncols + c

    dist = [math.inf] * (nrows * ncols)
    prev: list[int] = [-1] * (nrows * ncols)
    sr, sc = start
    dist[idx(sr, sc)] = 0.0
    pq: list[tuple[float, int, int]] = [(0.0, sr, sc)]

    while pq:
        d, r, c = heapq.heappop(pq)
        if (r, c) == goal:
            break
        if d > dist[idx(r, c)]:
            continue
        for dr, dc in _NEIGHBORS:
            nr, nc = r + dr, c + dc
            if not (0 <= nr < nrows and 0 <= nc < ncols):
                continue
            if blocked[nr][nc]:
                continue  # 건물 내부 통행 불가
            step = spacing * (math.sqrt(2) if dr and dc else 1.0)
            # 엣지 회피비율 = 양 끝 노드 평균
            edge_avoid = (int(avoid[r][c]) + int(avoid[nr][nc])) / 2.0
            cost = step * (1.0 + alpha * edge_avoid)
            nd = d + cost
            if nd < dist[idx(nr, nc)]:
                dist[idx(nr, nc)] = nd
                prev[idx(nr, nc)] = idx(r, c)
                heapq.heappush(pq, (nd, nr, nc))

    # 경로 복원
    gi = idx(*goal)
    if dist[gi] == math.inf:
        return [start, goal]
    path: list[tuple[int, int]] = []
    cur = gi
    while cur != -1:
        path.append((cur // ncols, cur % ncols))
        cur = prev[cur]
    path.reverse()
    return path
