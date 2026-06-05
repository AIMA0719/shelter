"""OSM 도보 네트워크 그래프 (Phase 2 정공법).

격자 프로토타입 대신, 실제 보행 가능한 도로(footway/path/residential 등)를 노드·엣지
그래프로 만든다. 교차점은 OSM 에서 노드를 공유하므로 좌표를 키로 묶으면 위상이
복원된다. 이 그래프 위에서 그늘 가중 다익스트라를 돌린다(osm_routing).

소스: Overpass(urllib) 실시간 추출, 또는 LineString GeoJSON 캐시 로드.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from collections import defaultdict
from dataclasses import dataclass, field

from .geo import haversine_m

DEFAULT_ENDPOINT = "https://overpass-api.de/api/interpreter"

# 보행 불가/제외 highway 유형
_EXCLUDED_HIGHWAY = {
    "motorway",
    "trunk",
    "motorway_link",
    "trunk_link",
    "construction",
    "proposed",
    "raceway",
    "bus_guideway",
    "escape",
}


_NEAREST_CELL_DEG = 0.002  # 약 200m 격자
# deg→m 하한(위도 1도 ≈ 111km, 경도는 더 짧음) — 링 종료 조건의 보수적 하한
_DEG_TO_M_LOWER = 88_000.0


@dataclass
class OsmGraph:
    """무방향 보행 그래프. nodes[i] = (lat, lon), adj[i] = [(j, 거리m), ...]."""

    nodes: list[tuple[float, float]] = field(default_factory=list)
    adj: dict[int, list[tuple[int, float]]] = field(default_factory=lambda: defaultdict(list))
    _index: dict[tuple[int, int], list[int]] | None = field(
        default=None, init=False, repr=False, compare=False
    )

    def node_count(self) -> int:
        return len(self.nodes)

    def edge_count(self) -> int:
        return sum(len(v) for v in self.adj.values()) // 2

    def _ensure_index(self) -> None:
        if self._index is not None:
            return
        grid: dict[tuple[int, int], list[int]] = defaultdict(list)
        cell = _NEAREST_CELL_DEG
        for i, (lat, lon) in enumerate(self.nodes):
            grid[(int(lat // cell), int(lon // cell))].append(i)
        self._index = grid

    def nearest_node(self, lat: float, lon: float) -> int:
        """주어진 좌표에 가장 가까운 노드 인덱스(그리드 인덱스 + 확장 링 탐색)."""
        if not self.nodes:
            raise ValueError("빈 그래프입니다.")
        self._ensure_index()
        assert self._index is not None
        cell = _NEAREST_CELL_DEG
        cell_m = cell * _DEG_TO_M_LOWER
        cx, cy = int(lat // cell), int(lon // cell)

        best_i, best_d = -1, float("inf")
        max_r = 64  # 약 12.8km 까지 탐색 후 그래도 못 찾으면 선형 폴백
        r = 0
        while r <= max_r:
            for ix, iy in _ring_cells(cx, cy, r):
                for ni in self._index.get((ix, iy), ()):
                    nlat, nlon = self.nodes[ni]
                    d = haversine_m(lat, lon, nlat, nlon)
                    if d < best_d:
                        best_i, best_d = ni, d
            # 링 r 까지 다 봤으면 미탐색 노드는 최소 r*cell_m 이상 떨어져 있으므로,
            # 현재 best 가 그보다 가까우면 확정(진짜 최근접).
            if best_i >= 0 and best_d <= r * cell_m:
                return best_i
            r += 1

        # 상한(max_r)까지도 확정하지 못했으면(성긴/먼 경우) 전수 스캔으로 정확성 보장.
        for ni, (nlat, nlon) in enumerate(self.nodes):
            d = haversine_m(lat, lon, nlat, nlon)
            if d < best_d:
                best_i, best_d = ni, d
        return best_i


def _ring_cells(cx: int, cy: int, r: int):
    """중심 (cx,cy) 에서 체비셰프 거리 r 인 셀들(경계 링만)."""
    if r == 0:
        yield (cx, cy)
        return
    for ix in range(cx - r, cx + r + 1):
        yield (ix, cy - r)
        yield (ix, cy + r)
    for iy in range(cy - r + 1, cy + r):
        yield (cx - r, iy)
        yield (cx + r, iy)


class _GraphBuilder:
    def __init__(self) -> None:
        self._coord_id: dict[tuple[float, float], int] = {}
        self.graph = OsmGraph()

    def node_id(self, lat: float, lon: float) -> int:
        key = (round(lat, 7), round(lon, 7))
        i = self._coord_id.get(key)
        if i is None:
            i = len(self._coord_id)
            self._coord_id[key] = i
            self.graph.nodes.append((lat, lon))
        return i

    def add_way(self, points: list[tuple[float, float]]) -> None:
        ids = [self.node_id(lat, lon) for lat, lon in points]
        for a, b in zip(ids, ids[1:]):
            if a == b:
                continue
            d = haversine_m(*self.graph.nodes[a], *self.graph.nodes[b])
            self.graph.adj[a].append((b, d))
            self.graph.adj[b].append((a, d))


def _is_walkable(tags: dict) -> bool:
    hw = tags.get("highway")
    if not hw or hw in _EXCLUDED_HIGHWAY:
        return False
    if tags.get("foot") == "no":
        return False
    if tags.get("access") in {"private", "no"}:
        return False
    return True


def parse_overpass_walk(payload: dict) -> OsmGraph:
    """Overpass JSON(out geom) → 보행 그래프."""
    builder = _GraphBuilder()
    for el in payload.get("elements", []):
        if el.get("type") != "way":
            continue
        if not _is_walkable(el.get("tags") or {}):
            continue
        geom = el.get("geometry") or []
        pts = [(float(p["lat"]), float(p["lon"])) for p in geom if "lat" in p and "lon" in p]
        if len(pts) >= 2:
            builder.add_way(pts)
    return builder.graph


def build_query(bbox: tuple[float, float, float, float]) -> str:
    """bbox=(min_lat, min_lon, max_lat, max_lon) → 보행 도로 Overpass QL."""
    min_lat, min_lon, max_lat, max_lon = bbox
    return (
        "[out:json][timeout:60];"
        f'way[highway][highway!~"^(motorway|trunk|motorway_link|trunk_link|construction|proposed|raceway)$"]'
        f"({min_lat},{min_lon},{max_lat},{max_lon});"
        "out geom;"
    )


def _fetch_payload(
    bbox: tuple[float, float, float, float], endpoint: str, timeout: float
) -> dict:
    data = urllib.parse.urlencode({"data": build_query(bbox)}).encode("utf-8")
    req = urllib.request.Request(
        endpoint, data=data, headers={"User-Agent": "shelter-shade-engine/0.1"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def fetch_walk_network(
    bbox: tuple[float, float, float, float],
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    timeout: float = 120.0,
) -> OsmGraph:
    """Overpass 에서 보행 네트워크를 받아 그래프로 변환."""
    return parse_overpass_walk(_fetch_payload(bbox, endpoint, timeout))


def overpass_to_geojson(payload: dict) -> dict:
    """Overpass JSON → 보행 가능 도로의 LineString FeatureCollection(캐시 저장용)."""
    features = []
    for el in payload.get("elements", []):
        if el.get("type") != "way":
            continue
        tags = el.get("tags") or {}
        if not _is_walkable(tags):
            continue
        geom = el.get("geometry") or []
        coords = [[float(p["lon"]), float(p["lat"])] for p in geom if "lat" in p and "lon" in p]
        if len(coords) >= 2:
            features.append(
                {
                    "type": "Feature",
                    "properties": {"highway": tags.get("highway"), "name": tags.get("name")},
                    "geometry": {"type": "LineString", "coordinates": coords},
                }
            )
    return {"type": "FeatureCollection", "features": features}


def fetch_walk_geojson(
    bbox: tuple[float, float, float, float],
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    timeout: float = 120.0,
) -> dict:
    """Overpass 에서 보행망을 받아 LineString GeoJSON 으로 반환(파일 캐시용)."""
    return overpass_to_geojson(_fetch_payload(bbox, endpoint, timeout))


def load_geojson_network(path: str) -> OsmGraph:
    """LineString/MultiLineString GeoJSON(좌표 [lon,lat]) → 보행 그래프(캐시 로드)."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    builder = _GraphBuilder()
    for feat in data.get("features", []):
        geom = feat.get("geometry") or {}
        gtype = geom.get("type")
        coords = geom.get("coordinates") or []
        lines: list[list] = []
        if gtype == "LineString":
            lines.append(coords)
        elif gtype == "MultiLineString":
            lines.extend(coords)
        else:
            continue
        for line in lines:
            pts = [(float(c[1]), float(c[0])) for c in line if len(c) >= 2]
            if len(pts) >= 2:
                builder.add_way(pts)
    return builder.graph
