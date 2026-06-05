from datetime import datetime, timedelta, timezone

from app.cache import LRUCache, route_cache_key
from app.models import LatLng

KST = timezone(timedelta(hours=9))
COORDS = [LatLng(lat=37.4975, lon=127.0270), LatLng(lat=37.4990, lon=127.0270)]


def _key(dt):
    return route_cache_key(COORDS, dt, "walk", 10.0, True)


def test_same_instant_same_key():
    a = _key(datetime(2026, 7, 15, 16, 0, tzinfo=KST))
    b = _key(datetime(2026, 7, 15, 16, 0, tzinfo=KST))
    assert a == b


def test_different_minute_different_key():
    # 코덱스 회귀: 같은 시(hour) 안의 다른 시각이 충돌하면 안 됨
    a = _key(datetime(2026, 7, 15, 16, 0, tzinfo=KST))
    b = _key(datetime(2026, 7, 15, 16, 45, tzinfo=KST))
    assert a != b


def test_timezone_normalized_to_utc():
    # 같은 절대 시각이면 타임존 표기가 달라도 같은 키
    kst = datetime(2026, 7, 15, 16, 0, tzinfo=KST)
    utc = kst.astimezone(timezone.utc)
    assert _key(kst) == _key(utc)


def test_different_offset_same_wallclock_different_key():
    # 벽시계는 같지만 타임존이 다르면(=다른 절대시각) 다른 키
    kst = datetime(2026, 7, 15, 16, 0, tzinfo=KST)
    utc_wall = datetime(2026, 7, 15, 16, 0, tzinfo=timezone.utc)
    assert _key(kst) != _key(utc_wall)


def test_lru_eviction():
    cache = LRUCache(max_entries=2)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.get("a")  # a 를 최근 사용으로
    cache.set("c", 3)  # b 가 밀려남
    assert cache.get("b") is None
    assert cache.get("a") == 1
    assert cache.get("c") == 3
