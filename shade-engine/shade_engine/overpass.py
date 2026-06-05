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
    """Overpass JSON(out geom) → Building 리스트."""
    buildings: list[Building] = []
    for el in payload.get("elements", []):
        tags = el.get("tags") or {}
        if "building" not in tags:
            continue
        geometry = el.get("geometry")
        if not geometry:
            continue
        ring = tuple(
            (float(pt["lat"]), float(pt["lon"])) for pt in geometry if "lat" in pt and "lon" in pt
        )
        if len(ring) < 3:
            continue
        height, estimated = estimate_height_m(tags)
        buildings.append(
            Building(
                ring=ring,
                height_m=height,
                height_estimated=estimated,
                osm_id=f"{el.get('type')}/{el.get('id')}",
                tags={k: str(v) for k, v in tags.items()},
            )
        )
    return buildings
