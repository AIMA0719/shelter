from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from shade_engine.demo import synthetic_scene

from app.buildings_repo import InMemoryBuildingsRepository
from app.config import Settings
from app.directions import StraightLineProvider
from app.main import create_app, set_service
from app.models import LatLng, RoutesRequest
from app.shade_service import ShadeService
from app.weather import StubWeatherProvider

KST = timezone(timedelta(hours=9))


def _service() -> ShadeService:
    _, buildings = synthetic_scene()
    return ShadeService(
        repo=InMemoryBuildingsRepository(buildings),
        provider=StraightLineProvider(),
        settings=Settings(),
    )


def _client() -> TestClient:
    set_service(_service())
    return TestClient(create_app())


def test_plan_route_options_returns_three():
    svc = _service()
    resp = svc.plan_route_options(
        RoutesRequest(
            origin=LatLng(lat=37.49750, lon=127.0270),
            destination=LatLng(lat=37.49900, lon=127.0270),
            depart_time=datetime(2026, 7, 15, 16, 0, tzinfo=KST),
        )
    )
    names = {o.name for o in resp.options}
    assert names == {"shortest", "balanced", "shadiest"}
    for o in resp.options:
        assert o.coords[0].lat == 37.49750
        assert len(o.segments) == max(0, len(o.coords) - 1) or len(o.segments) > 0
    assert resp.weather is not None


def test_routes_api_afternoon():
    client = _client()
    resp = client.post(
        "/v1/routes",
        json={
            "origin": {"lat": 37.49750, "lon": 127.0270},
            "destination": {"lat": 37.49900, "lon": 127.0270},
            "depart_time": "2026-07-15T16:00:00+09:00",
            "mode": "walk",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["options"]) == 3
    assert body["weather"]["source"] == "stub"
    # 그늘 최적이 최단보다 그늘이 적지 않아야 함
    by = {o["name"]: o for o in body["options"]}
    assert by["shadiest"]["shade_percent"] >= by["shortest"]["shade_percent"]


def test_routes_cache_hit_on_repeat():
    svc = _service()
    req = RoutesRequest(
        origin=LatLng(lat=37.49750, lon=127.0270),
        destination=LatLng(lat=37.49900, lon=127.0270),
        depart_time=datetime(2026, 7, 15, 16, 0, tzinfo=KST),
    )
    first = svc.plan_route_options(req)
    second = svc.plan_route_options(req)
    assert first.cached is False
    assert second.cached is True
    assert [o.shade_percent for o in first.options] == [o.shade_percent for o in second.options]


def test_routes_api_bike_mode():
    client = _client()
    resp = client.post(
        "/v1/routes",
        json={
            "origin": {"lat": 37.49750, "lon": 127.0270},
            "destination": {"lat": 37.49900, "lon": 127.0270},
            "mode": "bike",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["mode"] == "bike"


def test_weather_summer_hotter_than_winter():
    w = StubWeatherProvider()
    summer = w.badge(37.5, 127.0, datetime(2026, 7, 15, 14, 0, tzinfo=KST))
    winter = w.badge(37.5, 127.0, datetime(2026, 1, 15, 14, 0, tzinfo=KST))
    assert summer.temp_c > winter.temp_c
    assert summer.uv_index >= winter.uv_index
    assert summer.heat_advisory is True  # 한여름 한낮 → 폭염
