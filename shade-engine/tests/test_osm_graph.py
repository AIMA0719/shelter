import json

from shade_engine.osm_graph import (
    load_geojson_network,
    overpass_to_geojson,
    parse_overpass_walk,
)


def test_parse_shares_nodes_at_intersection():
    # 두 길이 좌표 B 를 공유 → 노드 3개, 엣지 2개
    payload = {
        "elements": [
            {
                "type": "way",
                "tags": {"highway": "footway"},
                "geometry": [
                    {"lat": 37.5, "lon": 127.0},
                    {"lat": 37.5, "lon": 127.001},
                ],
            },
            {
                "type": "way",
                "tags": {"highway": "residential"},
                "geometry": [
                    {"lat": 37.5, "lon": 127.001},
                    {"lat": 37.501, "lon": 127.001},
                ],
            },
            {  # 보행 불가 → 제외
                "type": "way",
                "tags": {"highway": "motorway"},
                "geometry": [
                    {"lat": 37.5, "lon": 127.0},
                    {"lat": 37.49, "lon": 127.0},
                ],
            },
        ]
    }
    g = parse_overpass_walk(payload)
    assert g.node_count() == 3
    assert g.edge_count() == 2


def test_foot_no_excluded():
    payload = {
        "elements": [
            {
                "type": "way",
                "tags": {"highway": "path", "foot": "no"},
                "geometry": [{"lat": 37.5, "lon": 127.0}, {"lat": 37.5, "lon": 127.001}],
            }
        ]
    }
    assert parse_overpass_walk(payload).node_count() == 0


def test_load_geojson_network(tmp_path):
    p = tmp_path / "net.geojson"
    p.write_text(
        '{"type":"FeatureCollection","features":['
        '{"type":"Feature","properties":{"highway":"footway"},'
        '"geometry":{"type":"LineString","coordinates":[[127.0,37.5],[127.001,37.5],[127.001,37.501]]}}'
        "]}",
        encoding="utf-8",
    )
    g = load_geojson_network(str(p))
    assert g.node_count() == 3
    assert g.edge_count() == 2


def test_overpass_to_geojson_roundtrip(tmp_path):
    payload = {
        "elements": [
            {
                "type": "way",
                "tags": {"highway": "footway"},
                "geometry": [
                    {"lat": 37.5, "lon": 127.0},
                    {"lat": 37.5, "lon": 127.001},
                    {"lat": 37.501, "lon": 127.001},
                ],
            },
            {  # motorway 는 geojson 변환 시 제외
                "type": "way",
                "tags": {"highway": "motorway"},
                "geometry": [{"lat": 37.5, "lon": 127.0}, {"lat": 37.49, "lon": 127.0}],
            },
        ]
    }
    fc = overpass_to_geojson(payload)
    assert len(fc["features"]) == 1  # 보행 가능한 way 만
    p = tmp_path / "net.geojson"
    p.write_text(json.dumps(fc), encoding="utf-8")
    g_direct = parse_overpass_walk(payload)
    g_loaded = load_geojson_network(str(p))
    assert g_loaded.node_count() == g_direct.node_count()
    assert g_loaded.edge_count() == g_direct.edge_count()


def test_nearest_node():
    payload = {
        "elements": [
            {
                "type": "way",
                "tags": {"highway": "footway"},
                "geometry": [{"lat": 37.5, "lon": 127.0}, {"lat": 37.5, "lon": 127.01}],
            }
        ]
    }
    g = parse_overpass_walk(payload)
    i = g.nearest_node(37.5, 127.0001)
    assert g.nodes[i] == (37.5, 127.0)


def test_nearest_node_index_matches_bruteforce():
    # 격자형 거리망(촘촘)에서 인덱스 결과 == 무차별 최근접
    from shade_engine.geo import haversine_m

    def way(pts):
        return {"type": "way", "tags": {"highway": "footway"}, "geometry": [{"lat": la, "lon": lo} for la, lo in pts]}

    elements = []
    for r in range(12):  # 위도선
        elements.append(way([(37.50 + r * 0.0009, 127.00 + c * 0.0011) for c in range(12)]))
    for c in range(12):  # 경도선
        elements.append(way([(37.50 + r * 0.0009, 127.00 + c * 0.0011) for r in range(12)]))
    g = parse_overpass_walk({"elements": elements})

    for qlat, qlon in [(37.5031, 127.0042), (37.5005, 127.0009), (37.5098, 127.0123), (37.5052, 127.0077)]:
        idx_i = g.nearest_node(qlat, qlon)
        brute_i = min(range(g.node_count()), key=lambda i: haversine_m(qlat, qlon, *g.nodes[i]))
        assert g.nodes[idx_i] == g.nodes[brute_i]
