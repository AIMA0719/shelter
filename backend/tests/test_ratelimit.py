from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app, set_service
from app.ratelimit import RateLimiter


def test_rate_limiter_unit():
    rl = RateLimiter(limit_per_min=3)
    # 같은 분(now=10s)에 3회 허용, 4회째 차단
    assert all(rl.allow("ip", 10.0) for _ in range(3))
    assert rl.allow("ip", 10.0) is False
    # 다음 분(now=70s)엔 다시 허용
    assert rl.allow("ip", 70.0) is True


def test_rate_limiter_zero_disables():
    rl = RateLimiter(limit_per_min=0)
    assert all(rl.allow("ip", 1.0) for _ in range(100))


def test_rate_limit_middleware_429():
    set_service(None)
    client = TestClient(create_app(settings=Settings(rate_limit_per_min=3)))
    codes = [client.get("/health").status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200]
    assert 429 in codes[3:]
    set_service(None)
