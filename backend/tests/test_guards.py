import threading

from fastapi.testclient import TestClient
from shade_engine.demo import synthetic_scene

from app.buildings_repo import InMemoryBuildingsRepository
from app.cache import LRUCache
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


def test_shade_rejects_too_long_route():
    client = _client()
    # 약 66km(위도 0.6도) → 50km 상한 초과
    resp = client.post(
        "/v1/shade",
        json={"coords": [{"lat": 37.0, "lon": 127.0}, {"lat": 37.6, "lon": 127.0}]},
    )
    assert resp.status_code == 422


def test_routes_reject_too_far():
    client = _client()
    # 약 55km → 거리 상한(12km) 초과
    resp = client.post(
        "/v1/routes",
        json={
            "origin": {"lat": 37.0, "lon": 127.0},
            "destination": {"lat": 37.5, "lon": 127.0},
        },
    )
    assert resp.status_code == 422


def test_lru_cache_thread_safe_smoke():
    cache = LRUCache(max_entries=100)

    def worker(base: int):
        for i in range(500):
            cache.set(f"{base}-{i}", i)
            cache.get(f"{base}-{i}")

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(cache) <= 100  # 락 보호로 크기 상한 유지, 예외 없이 완료
