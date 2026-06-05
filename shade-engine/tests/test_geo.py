import math

from shade_engine.geo import LocalProjection, bearing_deg, haversine_m


def test_projection_round_trip():
    proj = LocalProjection(lat0=37.5, lon0=127.0)
    lat, lon = 37.5012, 127.0034
    x, y = proj.to_xy(lat, lon)
    rlat, rlon = proj.to_latlon(x, y)
    assert math.isclose(rlat, lat, abs_tol=1e-9)
    assert math.isclose(rlon, lon, abs_tol=1e-9)


def test_projection_axes():
    proj = LocalProjection(lat0=37.5, lon0=127.0)
    east = proj.to_xy(37.5, 127.001)  # 동쪽
    north = proj.to_xy(37.501, 127.0)  # 북쪽
    assert east[0] > 0 and abs(east[1]) < 1e-6
    assert north[1] > 0 and abs(north[0]) < 1e-6


def test_haversine_one_degree_lat():
    d = haversine_m(37.0, 127.0, 38.0, 127.0)
    assert 111_000 < d < 111_400


def test_bearing_cardinal():
    assert math.isclose(bearing_deg(37.5, 127.0, 37.6, 127.0), 0.0, abs_tol=0.5)  # 북
    assert math.isclose(bearing_deg(37.5, 127.0, 37.5, 127.1), 90.0, abs_tol=0.5)  # 동
