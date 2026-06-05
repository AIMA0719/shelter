from datetime import datetime, timedelta, timezone

from shade_engine.demo import synthetic_scene
import pytest

from shade_engine.osm_graph import OsmGraph, parse_overpass_walk
from shade_engine.osm_routing import RouteNotFound, _dijkstra, plan_routes_osm
from shade_engine.sun import solar_position

KST = timezone(timedelta(hours=9))


def test_dijkstra_detours_around_sun_on_graph():
    # 다이아몬드: 0-1-3(1은 햇빛), 0-2-3(2는 그늘). 그늘 최적은 2를 거쳐야 한다.
    g = OsmGraph(nodes=[(0, 0), (0, 0), (0, 0), (0, 0)])
    for a, b in [(0, 1), (1, 3), (0, 2), (2, 3)]:
        g.adj[a].append((b, 10.0))
        g.adj[b].append((a, 10.0))
    avoid = [0.0, 1.0, 0.0, 0.0]  # 노드1만 회피 대상(햇빛)
    blocked = [False] * 4

    shadiest = _dijkstra(g, 0, 3, avoid, blocked, alpha=50.0)
    assert 1 not in shadiest
    assert 2 in shadiest
    assert shadiest[0] == 0 and shadiest[-1] == 3


def _two_street_network():
    # 동서로 떨어진 두 남북 거리(B: 서쪽 그늘대, A: 동쪽 햇빛) + 상하 연결로
    def way(pts):
        return {"type": "way", "tags": {"highway": "footway"}, "geometry": [{"lat": la, "lon": lo} for la, lo in pts]}

    lats = [37.4975, 37.4980, 37.4985, 37.4990]
    street_b = [(la, 127.0271) for la in lats]  # 건물 동쪽 가까이 → 오후 그늘
    street_a = [(la, 127.0276) for la in lats]  # 더 동쪽 → 햇빛
    connect_bottom = [(37.4975, 127.0271), (37.4975, 127.0276)]
    connect_top = [(37.4990, 127.0271), (37.4990, 127.0276)]
    return {"elements": [way(street_b), way(street_a), way(connect_bottom), way(connect_top)]}


def test_plan_routes_osm_invariants_and_shade_preference():
    graph = parse_overpass_walk(_two_street_network())
    _, buildings = synthetic_scene()
    origin = (37.4975, 127.0271)
    dest = (37.4990, 127.0271)
    sun = solar_position(origin[0], origin[1], datetime(2026, 7, 15, 16, 0, tzinfo=KST))

    options = plan_routes_osm(
        graph, origin, dest, buildings, sun.azimuth_deg, sun.altitude_deg
    )
    names = {o.name for o in options}
    assert names == {"shortest", "balanced", "shadiest"}

    by = {o.name: o for o in options}
    for o in options:
        assert o.coords[0] == origin
        assert o.coords[-1] == dest
        assert 0.0 <= o.sun_fraction <= 1.0

    # 그늘 최적은 최단보다 햇빛이 더 많지 않다.
    assert by["shadiest"].sun_fraction <= by["shortest"].sun_fraction + 1e-9


def test_plan_routes_osm_empty_graph_raises():
    with pytest.raises(RouteNotFound):
        plan_routes_osm(OsmGraph(), (37.5, 127.0), (37.6, 127.1), [], 264.0, 44.0)


def test_plan_routes_osm_raises_when_far_from_network():
    # 코덱스 회귀: 그래프가 출발/도착을 못 덮으면(먼 스냅) RouteNotFound.
    graph = parse_overpass_walk(_two_street_network())
    with pytest.raises(RouteNotFound):
        plan_routes_osm(graph, (37.6000, 127.2000), (37.6010, 127.2000), [], 264.0, 44.0)


def test_plan_routes_osm_raises_when_disconnected():
    # 코덱스 회귀: 두 개의 분리된 거리 → 한쪽에서 다른쪽으로 연결 안 됨.
    def way(pts):
        return {"type": "way", "tags": {"highway": "footway"}, "geometry": [{"lat": la, "lon": lo} for la, lo in pts]}

    payload = {"elements": [
        way([(37.5000, 127.0000), (37.5010, 127.0000)]),
        way([(37.5000, 127.0100), (37.5010, 127.0100)]),  # 분리된 별도 거리
    ]}
    graph = parse_overpass_walk(payload)
    with pytest.raises(RouteNotFound):
        plan_routes_osm(graph, (37.5000, 127.0000), (37.5000, 127.0100), [], 264.0, 44.0)
