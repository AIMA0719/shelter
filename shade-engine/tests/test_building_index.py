"""BuildingIndex(공간 인덱스)가 무차별 탐색과 동일한 결과를 주는지 검증."""

from shade_engine.raycast import BuildingIndex, ProjectedBuilding, is_point_shaded


def _square(cx, cy, half, height):
    ring = (
        (cx - half, cy - half),
        (cx + half, cy - half),
        (cx + half, cy + half),
        (cx - half, cy + half),
    )
    return ProjectedBuilding(ring_xy=ring, height_m=height, osm_id=f"{cx},{cy}")


def _grid_of_buildings():
    # 100m 간격 7x7 건물(높이 다양)
    blds = []
    for i in range(7):
        for j in range(7):
            blds.append(_square(i * 100.0, j * 100.0, 15.0, height=10.0 + (i + j) * 4.0))
    return blds


def test_index_matches_bruteforce():
    blds = _grid_of_buildings()
    index = BuildingIndex(blds)
    # 다양한 점·태양 방향에서 인덱스 결과 == 전체 무차별 결과
    for az in (0.0, 45.0, 135.0, 200.0, 270.0, 330.0):
        for px in range(-50, 700, 37):
            for py in range(-50, 700, 53):
                point = (float(px), float(py))
                brute = is_point_shaded(point, az, 40.0, blds, max_distance_m=300.0)
                fast = index.is_point_shaded(point, az, 40.0, max_distance_m=300.0)
                assert fast.shaded == brute.shaded, (point, az)
                assert fast.reason == brute.reason, (point, az)


def test_index_sun_below_shortcut():
    index = BuildingIndex(_grid_of_buildings())
    res = index.is_point_shaded((0.0, 0.0), 180.0, -3.0, max_distance_m=300.0)
    assert res.shaded and res.reason == "sun_below"


def test_index_empty():
    index = BuildingIndex([])
    res = index.is_point_shaded((0.0, 0.0), 180.0, 45.0, max_distance_m=300.0)
    assert not res.shaded and res.reason == "sunny"
