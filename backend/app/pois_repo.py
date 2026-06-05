"""쉼터 POI 저장소 (Phase 3).

그늘막·쿨링쉼터·음수대 등 폭염 대응 POI 를 GeoJSON(Point)에서 적재해 bbox 로
조회한다. 운영에서는 지자체 오픈데이터를 이 형식으로 정규화해 적재한다.
"""

from __future__ import annotations

import json

from .models import Poi


class GeoJSONPoisRepository:
    def __init__(self, path: str) -> None:
        self._pois: list[Poi] = _load(path)

    def query_bbox(
        self, min_lat: float, min_lon: float, max_lat: float, max_lon: float
    ) -> list[Poi]:
        return [
            p
            for p in self._pois
            if min_lat <= p.lat <= max_lat and min_lon <= p.lon <= max_lon
        ]

    def count(self) -> int:
        return len(self._pois)


def _load(path: str) -> list[Poi]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    pois: list[Poi] = []
    for feat in data.get("features", []):
        geom = feat.get("geometry") or {}
        props = feat.get("properties") or {}
        if geom.get("type") != "Point":
            continue
        coords = geom.get("coordinates") or []
        if len(coords) < 2:
            continue
        pois.append(
            Poi(
                lon=float(coords[0]),
                lat=float(coords[1]),
                type=str(props.get("type", "shade_shelter")),
                name=props.get("name"),
            )
        )
    return pois
