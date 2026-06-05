from shade_engine.overpass import build_query, parse_overpass


def test_build_query_contains_bbox_and_geom():
    q = build_query((37.49, 127.02, 37.50, 127.03))
    assert "way[building]" in q
    assert "relation[building]" in q
    assert "37.49,127.02,37.5,127.03" in q
    assert "out geom" in q


def test_parse_way_building():
    payload = {
        "elements": [
            {
                "type": "way",
                "id": 1,
                "tags": {"building": "yes", "building:levels": "5"},
                "geometry": [
                    {"lat": 37.5, "lon": 127.0},
                    {"lat": 37.5, "lon": 127.001},
                    {"lat": 37.501, "lon": 127.001},
                    {"lat": 37.501, "lon": 127.0},
                ],
            }
        ]
    }
    buildings = parse_overpass(payload)
    assert len(buildings) == 1
    assert buildings[0].height_m == 15.0  # 5층 × 3m
    assert buildings[0].height_estimated is True


def test_parse_relation_building_uses_outer_members():
    # 코덱스 회귀: relation[building] 의 geometry 는 members 에 있다.
    payload = {
        "elements": [
            {
                "type": "relation",
                "id": 42,
                "tags": {"building": "yes", "height": "30"},
                "members": [
                    {
                        "type": "way",
                        "role": "outer",
                        "geometry": [
                            {"lat": 37.5, "lon": 127.0},
                            {"lat": 37.5, "lon": 127.002},
                            {"lat": 37.502, "lon": 127.002},
                            {"lat": 37.502, "lon": 127.0},
                        ],
                    },
                    {
                        "type": "way",
                        "role": "inner",  # 구멍 → 무시
                        "geometry": [
                            {"lat": 37.5005, "lon": 127.0005},
                            {"lat": 37.5005, "lon": 127.001},
                            {"lat": 37.5008, "lon": 127.001},
                        ],
                    },
                ],
            }
        ]
    }
    buildings = parse_overpass(payload)
    assert len(buildings) == 1  # outer 1개만
    assert buildings[0].height_m == 30.0
    assert buildings[0].height_estimated is False
    assert buildings[0].osm_id == "relation/42"
