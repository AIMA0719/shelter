"""OSM 보행 그래프 기반 그늘 가중 라우팅 (Phase 2 정공법).

실제 보행로 그래프(osm_graph.OsmGraph) 위에서 엣지비용 = 거리 × (1 + α · 회피비율)
의 다익스트라를 돌린다. 회피 대상은 여름엔 햇빛, 겨울(prefer_sun)엔 그늘.
격자 프로토타입(routing.plan_routes)과 결과 형식(RouteOption)은 동일하다.
"""

from __future__ import annotations

import heapq
import math
from datetime import datetime

from .buildings import Building
from .geo import LocalProjection, haversine_m
from .raycast import BuildingIndex, ProjectedBuilding
from .routing import RouteOption, time_bucketed_suns

_MAX_SHADOW_DISTANCE_CAP_M = 1500.0
_DEFAULT_MAX_SNAP_M = 200.0


class RouteNotFound(ValueError):
    """보행 그래프로 경로를 찾지 못함(범위 밖·연결 끊김 등). 호출측은 폴백한다."""


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


def plan_routes_osm(
    graph,
    origin: tuple[float, float],
    dest: tuple[float, float],
    buildings: list[Building],
    sun_azimuth_deg: float,
    sun_altitude_deg: float,
    *,
    alphas: dict[str, float] | None = None,
    prefer_sun: bool = False,
    max_snap_m: float = _DEFAULT_MAX_SNAP_M,
    depart: datetime | None = None,
    speed_mps: float | None = None,
) -> list[RouteOption]:
    """OSM 보행 그래프에서 최단/균형/그늘(또는 햇빛) 경로 후보를 만든다.

    출발/도착이 그래프에서 max_snap_m 보다 멀거나, 그래프상 연결되지 않으면
    RouteNotFound 를 던진다(호출측이 격자 등으로 폴백). 잘못된 0거리/점프 경로 방지.
    """
    if alphas is None:
        third = "sunniest" if prefer_sun else "shadiest"
        alphas = {"shortest": 0.0, "balanced": 3.0, third: 12.0}

    if graph.node_count() == 0:
        raise RouteNotFound("빈 보행 그래프")

    lat0 = (origin[0] + dest[0]) / 2
    lon0 = (origin[1] + dest[1]) / 2
    proj = LocalProjection(lat0=lat0, lon0=lon0)
    projected = _project_buildings(buildings, proj)
    tallest = max((b.height_m for b in projected), default=0.0)

    # 노드별 햇빛/통행가능 계산. depart/speed 가 주어지면 출발점으로부터의 거리로
    # 도착 예상시각을 추정해 시간대별 태양을 적용(긴 경로의 태양 이동 반영),
    # 아니면 출발 태양 1회 값을 모든 노드에 사용(좁은 영역 근사 — 기존 동작 보존).
    index = BuildingIndex(projected)
    n = graph.node_count()
    node_dists = [haversine_m(origin[0], origin[1], lat, lon) for lat, lon in graph.nodes]
    node_suns = time_bucketed_suns(
        node_dists, origin, sun_azimuth_deg, sun_altitude_deg, depart=depart, speed_mps=speed_mps
    )
    sunny = [False] * n
    blocked = [False] * n
    for i, (lat, lon) in enumerate(graph.nodes):
        az, alt = node_suns[i]
        tan_alt = math.tan(math.radians(max(alt, 0.0)))
        max_dist = (
            min(_MAX_SHADOW_DISTANCE_CAP_M, tallest / tan_alt)
            if tan_alt > 1e-6
            else _MAX_SHADOW_DISTANCE_CAP_M
        )
        res = index.is_point_shaded(
            proj.to_xy(lat, lon),
            az,
            alt,
            max_distance_m=max(max_dist, 20.0),
        )
        sunny[i] = not res.shaded
        blocked[i] = res.reason == "inside_building"

    start = graph.nearest_node(*origin)
    goal = graph.nearest_node(*dest)

    # 스냅 거리 검증: 그래프가 출발/도착을 제대로 덮지 못하면 폴백시킨다.
    o_snap = haversine_m(origin[0], origin[1], *graph.nodes[start])
    d_snap = haversine_m(dest[0], dest[1], *graph.nodes[goal])
    if o_snap > max_snap_m or d_snap > max_snap_m:
        raise RouteNotFound(f"보행망 범위 밖(스냅 {o_snap:.0f}m/{d_snap:.0f}m)")
    if start == goal and haversine_m(origin[0], origin[1], dest[0], dest[1]) > max_snap_m:
        raise RouteNotFound("출발/도착이 같은 노드로 스냅됨(그래프가 너무 성김)")

    blocked[start] = False
    blocked[goal] = False

    # 회피값: 여름은 햇빛(sunny), 겨울은 그늘(not sunny)
    avoid = [
        1.0 if (sunny[i] if not prefer_sun else not sunny[i]) else 0.0 for i in range(n)
    ]

    options: list[RouteOption] = []
    for name, alpha in alphas.items():
        path = _dijkstra(graph, start, goal, avoid, blocked, alpha)
        if path is None:
            raise RouteNotFound("보행 그래프상 출발-도착이 연결되지 않음")
        coords = [graph.nodes[i] for i in path]
        if coords:
            coords[0] = origin
            coords[-1] = dest
        dist = sum(
            haversine_m(coords[k][0], coords[k][1], coords[k + 1][0], coords[k + 1][1])
            for k in range(len(coords) - 1)
        )
        sun_nodes = sum(1 for i in path if sunny[i])
        sun_frac = sun_nodes / len(path) if path else 0.0
        options.append(
            RouteOption(name=name, alpha=alpha, coords=coords, distance_m=dist, sun_fraction=sun_frac)
        )
    return options


def _dijkstra(
    graph, start: int, goal: int, avoid: list[float], blocked: list[bool], alpha: float
) -> list[int] | None:
    """엣지비용 = 거리 × (1 + α · 엣지회피비율). blocked 노드는 통행 불가.

    도달 불가면 None.
    """
    dist: dict[int, float] = {start: 0.0}
    prev: dict[int, int] = {}
    pq: list[tuple[float, int]] = [(0.0, start)]
    visited: set[int] = set()

    while pq:
        d, u = heapq.heappop(pq)
        if u == goal:
            break
        if u in visited:
            continue
        visited.add(u)
        for v, length in graph.adj.get(u, []):
            if blocked[v] and v != goal:
                continue
            edge_avoid = (avoid[u] + avoid[v]) / 2.0
            nd = d + length * (1.0 + alpha * edge_avoid)
            if nd < dist.get(v, math.inf):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))

    if goal not in dist:
        return None
    path = [goal]
    while path[-1] != start:
        path.append(prev[path[-1]])
    path.reverse()
    return path
