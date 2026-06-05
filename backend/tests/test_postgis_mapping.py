"""PostGIS 저장소의 순수 매핑/변환 검증(실제 DB 불필요)."""

import json

from shade_engine.buildings import Building

from app.db.ingest import building_to_wkt
from app.db.postgis_repo import _polygon_geojson_to_ring, _row_to_building


def test_polygon_geojson_to_ring():
    gj = json.dumps(
        {"type": "Polygon", "coordinates": [[[127.0, 37.5], [127.001, 37.5], [127.001, 37.501], [127.0, 37.5]]]}
    )
    ring = _polygon_geojson_to_ring(gj)
    assert ring[0] == (37.5, 127.0)  # (lat, lon) 순서로 변환
    assert ring[1] == (37.5, 127.001)


def test_row_to_building():
    gj = json.dumps(
        {"type": "Polygon", "coordinates": [[[127.0, 37.5], [127.001, 37.5], [127.001, 37.501]]]}
    )
    b = _row_to_building(33.0, True, gj, "way/1")
    assert b is not None
    assert b.height_m == 33.0
    assert b.height_estimated is True
    assert b.osm_id == "way/1"
    assert len(b.ring) >= 3


def test_row_to_building_degenerate_returns_none():
    gj = json.dumps({"type": "Polygon", "coordinates": [[[127.0, 37.5], [127.001, 37.5]]]})
    assert _row_to_building(10.0, False, gj, None) is None


def test_multipolygon_uses_first_exterior():
    gj = json.dumps(
        {
            "type": "MultiPolygon",
            "coordinates": [[[[127.0, 37.5], [127.001, 37.5], [127.001, 37.501], [127.0, 37.5]]]],
        }
    )
    ring = _polygon_geojson_to_ring(gj)
    assert len(ring) == 4


def test_building_to_wkt_closes_ring():
    b = Building(ring=((37.5, 127.0), (37.5, 127.001), (37.501, 127.001)), height_m=10.0)
    wkt = building_to_wkt(b)
    assert wkt.startswith("POLYGON((")
    # WKT 는 'lon lat' 순서, 닫힌 링(첫=끝)
    assert "127.0 37.5" in wkt
    assert wkt.count("127.0 37.5") >= 2  # 시작점이 끝에 다시 등장(닫힘)
