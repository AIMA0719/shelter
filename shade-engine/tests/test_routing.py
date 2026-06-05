from datetime import datetime, timedelta, timezone

from shade_engine.demo import synthetic_scene
from shade_engine.routing import _dijkstra, plan_routes
from shade_engine.sun import solar_position

KST = timezone(timedelta(hours=9))


def test_dijkstra_detours_around_sun():
    # 3x3 격자, 중앙(1,1)만 햇빛. 최단경로는 대각선으로 중앙을 지나지만,
    # 그늘 최적(alpha 큼)은 중앙을 우회해야 한다.
    sunny = [[False, False, False], [False, True, False], [False, False, False]]
    free = [[False, False, False], [False, False, False], [False, False, False]]
    shortest = _dijkstra((0, 0), (2, 2), 3, 3, 1.0, sunny, free, alpha=0.0)
    shadiest = _dijkstra((0, 0), (2, 2), 3, 3, 1.0, sunny, free, alpha=50.0)

    assert shortest[0] == (0, 0) and shortest[-1] == (2, 2)
    assert (1, 1) in shortest  # 최단은 햇빛 중앙을 통과
    assert (1, 1) not in shadiest  # 그늘 최적은 우회
    assert shadiest[0] == (0, 0) and shadiest[-1] == (2, 2)


def test_plan_routes_invariants():
    route, buildings = synthetic_scene()
    origin, dest = route[0], route[-1]
    sun = solar_position(origin[0], origin[1], datetime(2026, 7, 15, 16, 0, tzinfo=KST))

    options = plan_routes(
        origin, dest, buildings, sun.azimuth_deg, sun.altitude_deg, grid_spacing_m=20.0
    )
    names = {o.name for o in options}
    assert names == {"shortest", "balanced", "shadiest"}

    by_name = {o.name: o for o in options}
    for o in options:
        assert o.coords[0] == origin
        assert o.coords[-1] == dest
        assert 0.0 <= o.sun_fraction <= 1.0

    # 그늘 최적은 최단보다 햇빛이 더 많지 않다.
    assert by_name["shadiest"].sun_fraction <= by_name["shortest"].sun_fraction + 1e-9
    # 최단은 그늘 최적보다 길지 않다.
    assert by_name["shortest"].distance_m <= by_name["shadiest"].distance_m + 1.0


def test_plan_routes_prefers_shade_when_detour_helps():
    # 햇빛 영역 한가운데 그늘 한 동을 두고, 그 그늘을 지나가는 편이 이득이 되도록 배치.
    # 서쪽 태양 → 건물 동쪽에 그림자. origin/dest 를 건물 동쪽 그늘대 양 끝에 둔다.
    from shade_engine.buildings import Building

    # 동서로 짧은 벽(높이 40m) — 동쪽으로 긴 그림자
    wall = Building(
        ring=((37.5000, 127.0000), (37.5000, 127.0004), (37.5006, 127.0004), (37.5006, 127.0000)),
        height_m=40.0,
    )
    # 정서(az=270), 고도 45도 → 동쪽으로 약 40m 그림자
    origin = (37.5001, 127.0006)  # 건물 동쪽(그늘대 안)
    dest = (37.5005, 127.0006)
    options = plan_routes(origin, dest, [wall], 270.0, 45.0, grid_spacing_m=10.0)
    by_name = {o.name: o for o in options}
    # 그늘 최적 경로의 그늘 비율이 최단보다 작지 않아야 한다.
    assert by_name["shadiest"].shade_percent >= by_name["shortest"].shade_percent


def test_prefer_sun_renames_and_seeks_sun():
    # 겨울 모드: 그늘 대신 햇빛을 최대화. 옵션명에 'sunniest' 등장.
    sunny = [[False, False, False], [False, True, False], [False, False, False]]
    free = [[False] * 3 for _ in range(3)]
    # avoid=그늘(=not sunny)일 때, 햇빛(1,1)을 '지나가는' 경로가 유리해야 함
    avoid_shade = [[not sunny[r][c] for c in range(3)] for r in range(3)]
    path = _dijkstra((0, 0), (2, 2), 3, 3, 1.0, avoid_shade, free, alpha=50.0)
    assert (1, 1) in path  # 햇빛 노드를 통과(겨울엔 햇빛이 이득)

    route, buildings = synthetic_scene()
    options = plan_routes(
        route[0], route[-1], buildings, 264.0, 44.0, grid_spacing_m=20.0, prefer_sun=True
    )
    assert "sunniest" in {o.name for o in options}


def test_routes_do_not_cross_building():
    # 코덱스 회귀: 건물 내부를 통과하는 경로가 나오면 안 된다.
    from shade_engine.buildings import Building

    # 출발(서)~도착(동) 사이를 가로막는 건물(위도 37.4995~37.5005)
    bld = Building(
        ring=(
            (37.4995, 127.0000),
            (37.4995, 127.0010),
            (37.5005, 127.0010),
            (37.5005, 127.0000),
        ),
        height_m=40.0,
    )
    origin = (37.5000, 126.9990)
    dest = (37.5000, 127.0020)
    options = plan_routes(origin, dest, [bld], 270.0, 45.0, grid_spacing_m=15.0)

    for o in options:
        for lat, lon in o.coords:
            inside = 37.4995 < lat < 37.5005 and 127.0000 < lon < 127.0010
            assert not inside, f"{o.name} 경로가 건물 내부 통과: {(lat, lon)}"
