"""건물 데이터 저장소.

MVP 는 로컬 GeoJSON 을 메모리에 적재하고 bbox 로 필터링한다. 인터페이스를 통해
추후 PostGIS(공간 인덱스) 백엔드로 교체할 수 있다.
"""

from __future__ import annotations

from typing import Protocol

from shade_engine.buildings import Building, load_geojson


class BuildingsRepository(Protocol):
    def query_bbox(
        self, min_lat: float, min_lon: float, max_lat: float, max_lon: float
    ) -> list[Building]:
        ...

    def count(self) -> int:
        ...


class GeoJSONBuildingsRepository:
    """GeoJSON 파일을 1회 적재 후 bbox 교차로 필터링.

    건물 bbox 와 질의 bbox 가 겹치면 포함(보수적). 대량 데이터에는 부적합하므로
    서울 전역은 PostGIS 로 교체 예정.
    """

    def __init__(self, path: str) -> None:
        self._buildings: list[Building] = load_geojson(path)

    def query_bbox(
        self, min_lat: float, min_lon: float, max_lat: float, max_lon: float
    ) -> list[Building]:
        out: list[Building] = []
        for b in self._buildings:
            bmin_lat, bmin_lon, bmax_lat, bmax_lon = b.bbox()
            if bmax_lat < min_lat or bmin_lat > max_lat:
                continue
            if bmax_lon < min_lon or bmin_lon > max_lon:
                continue
            out.append(b)
        return out

    def count(self) -> int:
        return len(self._buildings)


class InMemoryBuildingsRepository:
    """테스트/주입용: 건물 리스트를 직접 보관."""

    def __init__(self, buildings: list[Building]) -> None:
        self._buildings = list(buildings)

    def query_bbox(
        self, min_lat: float, min_lon: float, max_lat: float, max_lon: float
    ) -> list[Building]:
        out: list[Building] = []
        for b in self._buildings:
            bmin_lat, bmin_lon, bmax_lat, bmax_lon = b.bbox()
            if bmax_lat < min_lat or bmin_lat > max_lat:
                continue
            if bmax_lon < min_lon or bmin_lon > max_lon:
                continue
            out.append(b)
        return out

    def count(self) -> int:
        return len(self._buildings)
