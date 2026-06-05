"""건물 모델 및 높이 추정.

그림자를 드리우는 캐스터의 1차 대상은 건물이다. OSM `building` 폴리곤의
`height`(미터) 태그를 우선 사용하고, 없으면 `building:levels` × 층고로 추정,
둘 다 없으면 기본값을 적용한다. 높이가 추정값인지 여부를 보존해 신뢰도 계산에 쓴다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

DEFAULT_LEVEL_HEIGHT_M = 3.0  # 층당 기본 층고
DEFAULT_BUILDING_HEIGHT_M = 9.0  # 높이/층수 정보가 전혀 없을 때 가정(약 3층)


@dataclass(frozen=True)
class Building:
    """건물 footprint(위경도 폴리곤)와 높이.

    ring: [(lat, lon), ...] 외곽 폴리곤. 닫힘 여부는 무관(자동 처리).
    height_m: 지면 기준 높이(미터).
    height_estimated: 높이가 태그 직접값이 아니라 추정값이면 True → 신뢰도 하락 요인.
    """

    ring: tuple[tuple[float, float], ...]
    height_m: float
    height_estimated: bool = False
    osm_id: str | None = None
    tags: dict[str, str] = field(default_factory=dict)

    def bbox(self) -> tuple[float, float, float, float]:
        """(min_lat, min_lon, max_lat, max_lon)."""
        lats = [p[0] for p in self.ring]
        lons = [p[1] for p in self.ring]
        return (min(lats), min(lons), max(lats), max(lons))


def estimate_height_m(tags: dict[str, Any]) -> tuple[float, bool]:
    """OSM 태그 → (높이 m, 추정여부).

    우선순위: height > building:levels×층고 > 기본값.
    """
    raw_height = tags.get("height")
    if raw_height is not None:
        parsed = _parse_meters(raw_height)
        if parsed is not None:
            return (parsed, False)

    levels = tags.get("building:levels") or tags.get("levels")
    if levels is not None:
        try:
            n = float(str(levels).strip())
            if n > 0:
                return (n * DEFAULT_LEVEL_HEIGHT_M, True)
        except ValueError:
            pass

    return (DEFAULT_BUILDING_HEIGHT_M, True)


def _parse_meters(value: Any) -> float | None:
    """'12', '12 m', '12.5m' 등 → float(미터). 파싱 실패 시 None."""
    s = str(value).strip().lower().replace("meters", "").replace("metres", "").replace("m", "")
    s = s.strip()
    try:
        v = float(s)
        return v if v > 0 else None
    except ValueError:
        return None


def load_geojson(path: str) -> list[Building]:
    """GeoJSON(FeatureCollection) → 건물 리스트.

    Polygon/MultiPolygon Feature 의 외곽 링만 사용. 좌표는 [lon, lat] (GeoJSON 표준).
    properties 의 height/building:levels 로 높이를 추정한다.
    """
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return _features_to_buildings(data.get("features", []))


def _features_to_buildings(features: list[dict]) -> list[Building]:
    buildings: list[Building] = []
    for feat in features:
        geom = feat.get("geometry") or {}
        props = feat.get("properties") or {}
        gtype = geom.get("type")
        coords = geom.get("coordinates") or []

        rings: list[list] = []
        if gtype == "Polygon" and coords:
            rings.append(coords[0])
        elif gtype == "MultiPolygon":
            rings.extend(poly[0] for poly in coords if poly)
        else:
            continue

        height, estimated = estimate_height_m(props)
        osm_id = props.get("id") or feat.get("id")
        tags = {k: str(v) for k, v in props.items()}
        for ring_coords in rings:
            ring = tuple((float(pt[1]), float(pt[0])) for pt in ring_coords if len(pt) >= 2)
            if len(ring) >= 3:
                buildings.append(
                    Building(
                        ring=ring,
                        height_m=height,
                        height_estimated=estimated,
                        osm_id=str(osm_id) if osm_id is not None else None,
                        tags=tags,
                    )
                )
    return buildings
