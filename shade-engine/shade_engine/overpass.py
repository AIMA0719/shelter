"""OSM Overpass API 에서 건물 footprint 추출 (선택적 확장).

표준 라이브러리(urllib)만 사용한다. 네트워크가 필요하므로 코어 테스트에서는
쓰지 않으며, 실제 권역(예: 강남) 데이터를 받을 때만 호출한다.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

from .buildings import Building, estimate_height_m

DEFAULT_ENDPOINT = "https://overpass-api.de/api/interpreter"


def build_query(bbox: tuple[float, float, float, float]) -> str:
    """bbox=(min_lat, min_lon, max_lat, max_lon) → Overpass QL (geometry 포함)."""
    min_lat, min_lon, max_lat, max_lon = bbox
    return (
        "[out:json][timeout:60];"
        f"(way[building]({min_lat},{min_lon},{max_lat},{max_lon});"
        f"relation[building]({min_lat},{min_lon},{max_lat},{max_lon}););"
        "out geom;"
    )


def fetch_buildings(
    bbox: tuple[float, float, float, float],
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    timeout: float = 90.0,
) -> list[Building]:
    """Overpass 에서 건물을 받아 Building 리스트로 변환."""
    query = build_query(bbox)
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    req = urllib.request.Request(endpoint, data=data, headers={"User-Agent": "shelter-shade-engine/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (신뢰된 엔드포인트)
        payload = json.loads(resp.read().decode("utf-8"))
    return parse_overpass(payload)


def parse_overpass(payload: dict) -> list[Building]:
    """Overpass JSON(out geom) → Building 리스트.

    way 는 top-level `geometry`, relation(멀티폴리곤)은 각 `members` 의 outer
    멤버에 geometry 가 담긴다. 관계형 건물의 외곽 링을 각각 캐스터로 사용한다
    (내부 구멍은 그림자 근사에서 무시 — 약간의 과대 그늘만 발생).
    """
    buildings: list[Building] = []
    for el in payload.get("elements", []):
        tags = el.get("tags") or {}
        if "building" not in tags:
            continue

        rings_raw = _element_rings(el)
        if not rings_raw:
            continue

        height, estimated = estimate_height_m(tags)
        osm_id = f"{el.get('type')}/{el.get('id')}"
        str_tags = {k: str(v) for k, v in tags.items()}
        for geom in rings_raw:
            ring = tuple(
                (float(pt["lat"]), float(pt["lon"])) for pt in geom if "lat" in pt and "lon" in pt
            )
            if len(ring) >= 3:
                buildings.append(
                    Building(
                        ring=ring,
                        height_m=height,
                        height_estimated=estimated,
                        osm_id=osm_id,
                        tags=str_tags,
                    )
                )
    return buildings


def _element_rings(el: dict) -> list[list]:
    """Overpass 요소에서 외곽 링 좌표 리스트들을 추출한다."""
    if el.get("type") == "relation":
        rings = [
            m["geometry"]
            for m in el.get("members", [])
            if m.get("role") == "outer" and m.get("geometry")
        ]
        if rings:
            return rings
    geometry = el.get("geometry")
    return [geometry] if geometry else []


def buildings_to_geojson(payload: dict) -> dict:
    """Overpass JSON → 건물 Polygon FeatureCollection(좌표 [lon,lat]).

    backend 의 load_geojson 이 읽을 수 있도록 height/building:levels 태그를 보존해,
    파일을 다시 로드해도 동일하게 높이를 추정한다.
    """
    features = []
    for el in payload.get("elements", []):
        tags = el.get("tags") or {}
        if "building" not in tags:
            continue
        props = {"id": f"{el.get('type')}/{el.get('id')}"}
        for k in ("height", "building", "building:levels", "levels", "name"):
            if k in tags:
                props[k] = str(tags[k])
        for ring in _element_rings(el):
            coords = [[float(p["lon"]), float(p["lat"])] for p in ring if "lat" in p and "lon" in p]
            if len(coords) >= 3:
                if coords[0] != coords[-1]:
                    coords.append(coords[0])  # 링 닫기
                features.append(
                    {
                        "type": "Feature",
                        "properties": props,
                        "geometry": {"type": "Polygon", "coordinates": [coords]},
                    }
                )
    return {"type": "FeatureCollection", "features": features}


def fetch_buildings_geojson(
    bbox: tuple[float, float, float, float],
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    timeout: float = 90.0,
) -> dict:
    """Overpass 에서 건물을 받아 Polygon GeoJSON 으로 반환(파일 캐시용)."""
    query = build_query(bbox)
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    req = urllib.request.Request(
        endpoint, data=data, headers={"User-Agent": "shelter-shade-engine/0.1"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        payload = json.loads(resp.read().decode("utf-8"))
    return buildings_to_geojson(payload)
