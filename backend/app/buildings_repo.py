"""건물 데이터 저장소.

MVP 는 로컬 GeoJSON 을 메모리에 적재하되, 위경도 그리드 공간 인덱스로 bbox 질의를
O(전체 건물)이 아닌 O(주변 셀)로 처리한다(서울 전역 확장 대비). 추후 PostGIS(GiST)
백엔드로 교체할 수 있는 동일 인터페이스를 유지한다.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Protocol

from shade_engine.buildings import Building, load_geojson

_CELL_DEG = 0.003  # 약 330m 격자


class BuildingsRepository(Protocol):
    def query_bbox(
        self, min_lat: float, min_lon: float, max_lat: float, max_lon: float
    ) -> list[Building]:
        ...

    def count(self) -> int:
        ...


class _IndexedBuildings:
    """그리드 공간 인덱스 기반 bbox 질의 공통 구현."""

    def _build_index(self, buildings: list[Building]) -> None:
        self._buildings = buildings
        self._grid: dict[tuple[int, int], list[Building]] = defaultdict(list)
        for b in buildings:
            min_lat, min_lon, max_lat, max_lon = b.bbox()
            for cx in range(int(min_lat // _CELL_DEG), int(max_lat // _CELL_DEG) + 1):
                for cy in range(int(min_lon // _CELL_DEG), int(max_lon // _CELL_DEG) + 1):
                    self._grid[(cx, cy)].append(b)

    def query_bbox(
        self, min_lat: float, min_lon: float, max_lat: float, max_lon: float
    ) -> list[Building]:
        seen: dict[int, Building] = {}
        for cx in range(int(min_lat // _CELL_DEG), int(max_lat // _CELL_DEG) + 1):
            for cy in range(int(min_lon // _CELL_DEG), int(max_lon // _CELL_DEG) + 1):
                for b in self._grid.get((cx, cy), ()):
                    bid = id(b)
                    if bid in seen:
                        continue
                    bmin_lat, bmin_lon, bmax_lat, bmax_lon = b.bbox()
                    if bmax_lat < min_lat or bmin_lat > max_lat:
                        continue
                    if bmax_lon < min_lon or bmin_lon > max_lon:
                        continue
                    seen[bid] = b
        return list(seen.values())

    def count(self) -> int:
        return len(self._buildings)


class GeoJSONBuildingsRepository(_IndexedBuildings):
    """GeoJSON 파일을 1회 적재 후 그리드 인덱스로 질의."""

    def __init__(self, path: str) -> None:
        self._build_index(load_geojson(path))


class InMemoryBuildingsRepository(_IndexedBuildings):
    """테스트/주입용: 건물 리스트를 직접 인덱싱."""

    def __init__(self, buildings: list[Building]) -> None:
        self._build_index(list(buildings))
