from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.buildings_repo import InMemoryBuildingsRepository
from app.config import Settings
from app.directions import StraightLineProvider
from app.main import create_app, set_service
from app.shade_service import ShadeService
from shade_engine.demo import synthetic_scene

KST = timezone(timedelta(hours=9))


def _client_with_synthetic() -> TestClient:
    _, buildings = synthetic_scene()
    svc = ShadeService(
        repo=InMemoryBuildingsRepository(buildings),
        provider=StraightLineProvider(),
        settings=Settings(),
    )
    set_service(svc)
    return TestClient(create_app())


def _route_payload():
    route, _ = synthetic_scene()
    return [{"lat": lat, "lon": lon} for lat, lon in route]


def test_health_ok():
    client = _client_with_synthetic()
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["buildings_loaded"] >= 3


def test_shade_afternoon():
    client = _client_with_synthetic()
    resp = client.post(
        "/v1/shade",
        json={"coords": _route_payload(), "depart_time": "2026-07-15T16:00:00+09:00"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["shade_percent"] > 50.0
    assert body["sample_count"] > 0
    assert len(body["segments"]) == body["sample_count"] - 1
    assert body["segments"][0]["shaded"] in (True, False)


def test_shade_requires_route_input():
    client = _client_with_synthetic()
    # origin/destination 도 coords 도 없음 → 422 (검증 실패)
    resp = client.post("/v1/shade", json={"depart_time": "2026-07-15T16:00:00+09:00"})
    assert resp.status_code == 422


def test_shade_origin_destination():
    client = _client_with_synthetic()
    resp = client.post(
        "/v1/shade",
        json={
            "origin": {"lat": 37.49750, "lon": 127.0270},
            "destination": {"lat": 37.49900, "lon": 127.0270},
            "depart_time": "2026-07-15T16:00:00+09:00",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["provider"] == "straight"


def test_invalid_latlng_rejected():
    client = _client_with_synthetic()
    resp = client.post(
        "/v1/shade",
        json={"coords": [{"lat": 200, "lon": 127.0}, {"lat": 37.5, "lon": 127.0}]},
    )
    assert resp.status_code == 422
