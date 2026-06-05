from fastapi.testclient import TestClient
from shade_engine.demo import synthetic_scene

from app.buildings_repo import InMemoryBuildingsRepository
from app.config import Settings
from app.directions import StraightLineProvider
from app.main import create_app, set_service
from app.shade_service import ShadeService


def _client() -> TestClient:
    _, buildings = synthetic_scene()
    set_service(
        ShadeService(
            repo=InMemoryBuildingsRepository(buildings),
            provider=StraightLineProvider(),
            settings=Settings(),
        )
    )
    return TestClient(create_app())


_OD = {
    "origin": {"lat": 37.49750, "lon": 127.0270},
    "destination": {"lat": 37.49900, "lon": 127.0270},
}


def test_departure_suggest_summer_prefers_afternoon():
    client = _client()
    resp = client.post(
        "/v1/departure-suggest",
        json={**_OD, "date": "2026-07-15", "hours": [8, 12, 16], "prefer": "shade"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["candidates"]) == 3
    # 서편 고층 → 오후가 가장 그늘 → best 는 16시
    assert body["best"]["depart_time"].startswith("2026-07-15T16")


def test_departure_suggest_winter_mode_prefers_sun():
    client = _client()
    resp = client.post(
        "/v1/departure-suggest",
        json={**_OD, "date": "2026-07-15", "hours": [8, 12, 16], "prefer": "sun"},
    )
    body = resp.json()
    assert body["prefer"] == "sun"
    assert not body["best"]["depart_time"].startswith("2026-07-15T16")


def test_routes_winter_sun_mode():
    client = _client()
    resp = client.post("/v1/routes", json={**_OD, "prefer": "sun"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["prefer"] == "sun"
    assert "sunniest" in {o["name"] for o in body["options"]}
    for o in body["options"]:
        assert 0.0 <= o["comfort"] <= 100.0


def test_pois_within_bbox():
    client = _client()
    resp = client.get(
        "/v1/pois",
        params={"min_lat": 37.497, "min_lon": 127.026, "max_lat": 37.499, "max_lon": 127.028},
    )
    assert resp.status_code == 200
    pois = resp.json()["pois"]
    assert len(pois) == 3  # 먼 POI 제외
    assert {p["type"] for p in pois} == {"shade_shelter", "cooling_center", "water_fountain"}


def test_pois_invalid_bbox():
    client = _client()
    resp = client.get(
        "/v1/pois",
        params={"min_lat": 37.5, "min_lon": 127.03, "max_lat": 37.49, "max_lon": 127.02},
    )
    assert resp.status_code == 422
