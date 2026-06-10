"""Phase 4 개선 회귀 테스트.

- 경로 옵션 ETA(duration_min)
- 가로수 그림자 백엔드 연동
- KMA UV 누락 시 stub 추정으로 채움
- 레이트리미터 키 누수(만료 창 청소)
- CORS 출처 파싱
- 거리 상한 초과 메시지(실제 12km 캡 반영)
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from shade_engine.demo import synthetic_scene
from shade_engine.trees import Tree

from app.buildings_repo import InMemoryBuildingsRepository
from app.config import Settings
from app.directions import StraightLineProvider
from app.main import create_app, set_service
from app.models import LatLng, ShadeRequest
from app.ratelimit import RateLimiter
from app.shade_service import ShadeService
from app.trees_repo import InMemoryTreesRepository
from app.weather import KMAWeatherProvider, WeatherInfo


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


# --- ETA -------------------------------------------------------------------


def test_route_options_include_eta_duration():
    resp = _client().post("/v1/routes", json={**_OD, "mode": "walk"})
    assert resp.status_code == 200
    for o in resp.json()["options"]:
        assert o["duration_min"] >= 0
        if o["distance_m"] > 0:
            assert o["duration_min"] > 0  # 거리>0 이면 예상시간도 양수


def test_bike_eta_shorter_than_walk_for_same_distance():
    # 자전거(4.2 m/s)는 같은 거리에서 도보(1.3 m/s)보다 예상시간이 짧다.
    client = _client()
    walk = client.post("/v1/routes", json={**_OD, "mode": "walk"}).json()["options"][0]
    bike = client.post("/v1/routes", json={**_OD, "mode": "bike"}).json()["options"][0]
    # 같은 최단 경로 거리라면 자전거가 더 빠르다(거리 동일 가정).
    if abs(walk["distance_m"] - bike["distance_m"]) < 1.0:
        assert bike["duration_min"] < walk["duration_min"]


# --- 가로수 연동 -------------------------------------------------------------


def test_trees_increase_route_shade():
    """경로 위에 가로수를 놓으면 그늘%가 올라가야 한다(가로수 캐스터 백엔드 연동)."""
    coords = [LatLng(lat=37.5000, lon=127.0000), LatLng(lat=37.5009, lon=127.0000)]
    depart = datetime(2026, 7, 15, 3, 0, tzinfo=timezone.utc)  # 12:00 KST, 태양 높음

    sunny = ShadeService(
        repo=InMemoryBuildingsRepository([]),
        provider=StraightLineProvider(),
        settings=Settings(),
    ).compute(ShadeRequest(coords=coords, depart_time=depart))
    assert sunny.shade_percent == 0.0  # 건물·가로수 없음 → 완전 햇빛

    tree = Tree(lat=37.50045, lon=127.0000, height_m=20.0, canopy_radius_m=30.0)
    shaded = ShadeService(
        repo=InMemoryBuildingsRepository([]),
        provider=StraightLineProvider(),
        settings=Settings(),
        trees=InMemoryTreesRepository([tree]),
    ).compute(ShadeRequest(coords=coords, depart_time=depart))
    assert shaded.shade_percent > sunny.shade_percent


# --- UV 폴백 ---------------------------------------------------------------


def test_kma_fills_uv_from_stub_when_observation_lacks_it(monkeypatch):
    """실측 기온은 있으나 UV 가 없으면 계절/시각 추정으로 채운다(comfort 가중치 보존)."""
    provider = KMAWeatherProvider("dummy-key")
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(
        provider,
        "_fetch",
        lambda lat, lon, dt: WeatherInfo(
            temp_c=30.0, uv_index=None, heat_advisory=False, source="kma"
        ),
    )
    info = provider.badge(37.5665, 126.9780, now)
    assert info.temp_c == 30.0
    assert info.uv_index is not None  # null 금지 — stub 으로 채움
    assert info.source == "kma"


# --- 레이트리미터 키 누수 ----------------------------------------------------


def test_rate_limiter_evicts_stale_keys_on_minute_change():
    rl = RateLimiter(limit_per_min=5)
    rl.allow("a", 10.0)
    rl.allow("b", 10.0)
    assert len(rl._window) == 2
    rl.allow("c", 70.0)  # 다음 분 → a,b 창 만료 → 청소
    assert set(rl._window) == {"c"}


# --- CORS 파싱 -------------------------------------------------------------


def test_cors_origin_list_parsing():
    assert Settings(cors_origins="*").cors_origin_list() == ["*"]
    assert Settings(cors_origins="").cors_origin_list() == ["*"]
    assert Settings(cors_origins="https://a.com, https://b.com").cors_origin_list() == [
        "https://a.com",
        "https://b.com",
    ]


# --- 거리 상한 메시지 --------------------------------------------------------


def test_routes_too_far_message_reflects_real_cap():
    """12km 캡 초과 메시지가 실제 캡(12km)을 반영해야 한다(예전 '30km' 오기 회귀)."""
    resp = _client().post(
        "/v1/routes",
        json={
            "origin": {"lat": 37.50, "lon": 127.00},
            "destination": {"lat": 37.62, "lon": 127.10},  # ~16km
        },
    )
    assert resp.status_code == 422
    assert "12km" in resp.json()["detail"]
    assert "30km" not in resp.json()["detail"]
