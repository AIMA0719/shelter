from shade_engine.raycast import ProjectedBuilding, is_point_shaded


def square(cx, cy, half, height, *, estimated=False, osm_id="b"):
    ring = (
        (cx - half, cy - half),
        (cx + half, cy - half),
        (cx + half, cy + half),
        (cx - half, cy + half),
    )
    return ProjectedBuilding(ring_xy=ring, height_m=height, height_estimated=estimated, osm_id=osm_id)


# 태양은 정북(az=0), 고도 45도. 그늘 임계 = 거리 × tan(45) = 거리.


def test_tall_building_toward_sun_shades():
    b = square(0, 20, 5, height=30)  # 북쪽 15~25m, 충분히 높음
    res = is_point_shaded((0, 0), 0.0, 45.0, [b])
    assert res.shaded
    assert res.reason == "building"
    assert res.blocker_distance_m is not None and 14 < res.blocker_distance_m < 16


def test_short_building_does_not_shade():
    b = square(0, 20, 5, height=10)  # 임계(≈15) 미만
    res = is_point_shaded((0, 0), 0.0, 45.0, [b])
    assert not res.shaded
    assert res.reason == "sunny"


def test_building_away_from_sun_does_not_shade():
    b = square(0, -20, 5, height=50)  # 남쪽 → 정북 태양을 가리지 못함
    res = is_point_shaded((0, 0), 0.0, 45.0, [b])
    assert not res.shaded


def test_point_inside_building():
    b = square(0, 0, 10, height=30)
    res = is_point_shaded((0, 0), 0.0, 45.0, [b])
    assert res.shaded
    assert res.reason == "inside_building"


def test_sun_below_horizon_is_shade():
    b = square(0, 20, 5, height=30)
    res = is_point_shaded((0, 0), 0.0, -5.0, [b])
    assert res.shaded
    assert res.reason == "sun_below"


def test_low_sun_long_shadow():
    # 고도 10도면 그림자 임계가 완만 → 먼 건물도 그늘 형성
    b = square(0, 100, 5, height=30)  # 임계 = 95*tan10 ≈ 16.7 < 30
    res = is_point_shaded((0, 0), 0.0, 10.0, [b], max_distance_m=500)
    assert res.shaded


def test_estimated_height_reduces_confidence_near_threshold():
    b = square(0, 20, 5, height=16, estimated=True)  # 임계≈15, 1.2배(18) 미만
    res = is_point_shaded((0, 0), 0.0, 45.0, [b])
    assert res.shaded
    assert res.confidence < 1.0
