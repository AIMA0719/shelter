from shade_engine.comfort import comfort_score


def test_full_shade_is_max_comfort():
    assert comfort_score(1.0, temp_c=35.0, uv_index=11.0) == 100.0


def test_more_shade_more_comfort():
    low = comfort_score(0.2, temp_c=33.0, uv_index=9.0)
    high = comfort_score(0.9, temp_c=33.0, uv_index=9.0)
    assert high > low


def test_hotter_less_comfort_for_same_sun():
    cool = comfort_score(0.5, temp_c=24.0, uv_index=5.0)
    hot = comfort_score(0.5, temp_c=34.0, uv_index=5.0)
    assert hot < cool


def test_bounds():
    assert 0.0 <= comfort_score(0.0, temp_c=40.0, uv_index=11.0) <= 100.0
    assert comfort_score(0.0, temp_c=None, uv_index=None) <= 100.0
