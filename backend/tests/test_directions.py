from app.directions import KakaoDirectionsProvider, StraightLineProvider, get_provider
from app.config import Settings
from app.models import LatLng


def test_straight_line_endpoints_and_density():
    provider = StraightLineProvider(step_m=25.0)
    origin = LatLng(lat=37.4975, lon=127.0270)
    dest = LatLng(lat=37.4990, lon=127.0270)  # 약 167m 북쪽
    pts = provider.route(origin, dest, "walk")
    assert len(pts) >= 2
    assert pts[0].lat == origin.lat and pts[0].lon == origin.lon
    assert abs(pts[-1].lat - dest.lat) < 1e-9
    # 약 167m / 25m ≈ 6구간 → 7점 이상
    assert len(pts) >= 6


def test_straight_line_same_point():
    provider = StraightLineProvider()
    p = LatLng(lat=37.5, lon=127.0)
    pts = provider.route(p, p, "walk")
    assert len(pts) >= 2  # 최소 출발/도착


def test_get_provider_defaults_to_straight():
    assert get_provider(Settings()).name == "straight"


def test_kakao_requires_key():
    import pytest

    with pytest.raises(ValueError):
        KakaoDirectionsProvider("")


def test_kakao_parse_vertexes():
    payload = {
        "routes": [
            {"sections": [{"roads": [{"vertexes": [127.0, 37.5, 127.001, 37.501]}]}]}
        ]
    }
    pts = KakaoDirectionsProvider._parse(payload)
    assert len(pts) == 2
    assert pts[0].lon == 127.0 and pts[0].lat == 37.5
    assert pts[1].lon == 127.001 and pts[1].lat == 37.501
