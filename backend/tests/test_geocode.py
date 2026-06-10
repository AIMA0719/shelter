"""지오코딩 프록시(/v1/geocode) 테스트 — 파싱, 캐시, 스로틀, 엔드포인트."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.geocode import NominatimGeocoder, parse_reverse, parse_search_results
from app.main import create_app, set_geocoder

SEARCH_BODY = json.dumps(
    [
        {
            "lat": "37.4975",
            "lon": "127.0270",
            "name": "강남구청",
            "display_name": "강남구청, 학동로, 논현동, 강남구, 서울특별시, 대한민국",
        },
        {
            # name 없음 → display_name 첫 쉼표 구간을 이름으로
            "lat": "37.5172",
            "lon": "127.0473",
            "display_name": "코엑스, 영동대로, 삼성동, 강남구, 서울특별시, 대한민국",
        },
        {
            # lat 누락 → 건너뜀
            "display_name": "위도경도없음",
        },
    ]
)

REVERSE_BODY = json.dumps(
    {"lat": "37.4975", "lon": "127.0270", "display_name": "강남구청, 학동로, 강남구"}
)


# ----------------------------------------------------------------------
# 파싱
# ----------------------------------------------------------------------


def test_parse_search_results():
    results = parse_search_results(SEARCH_BODY)
    assert len(results) == 2
    assert results[0].name == "강남구청"
    assert results[0].lat == 37.4975
    assert results[0].address.startswith("강남구청,")
    assert results[1].name == "코엑스"  # display_name 폴백


def test_parse_search_results_garbage():
    assert parse_search_results("garbage {{{") == []
    assert parse_search_results("{}") == []  # 배열 아님
    assert parse_search_results("[]") == []


def test_parse_search_results_blank_name_falls_back():
    body = json.dumps(
        [{"lat": "37.5665", "lon": "126.9780", "name": "", "display_name": "서울특별시청, 중구"}]
    )
    results = parse_search_results(body)
    assert results[0].name == "서울특별시청"


def test_parse_reverse():
    assert parse_reverse(REVERSE_BODY) == "강남구청, 학동로, 강남구"
    assert parse_reverse("{}") is None
    assert parse_reverse("garbage {{{") is None


# ----------------------------------------------------------------------
# 캐시 / 스로틀 / 오류 강등
# ----------------------------------------------------------------------


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def _geocoder(fetch, clock=None, **kw) -> NominatimGeocoder:
    clock = clock or FakeClock()
    return NominatimGeocoder(fetch=fetch, clock=clock, sleep=lambda s: None, **kw)


def test_search_cache_hit_skips_upstream():
    calls = []

    def fetch(url: str) -> str:
        calls.append(url)
        return SEARCH_BODY

    geo = _geocoder(fetch)
    first = geo.search("강남구청")
    second = geo.search("강남구청")
    assert len(calls) == 1  # 두 번째는 캐시
    assert first == second


def test_search_cache_ttl_expiry():
    calls = []
    clock = FakeClock()

    def fetch(url: str) -> str:
        calls.append(url)
        return SEARCH_BODY

    geo = _geocoder(fetch, clock=clock, cache_ttl_s=100.0)
    geo.search("강남구청")
    clock.t = 101.0
    geo.search("강남구청")
    assert len(calls) == 2  # TTL 만료 → 업스트림 재호출


def test_reverse_caches_none_result():
    """결과 없음(None)도 캐시해 같은 좌표 반복 호출이 업스트림을 때리지 않는다."""
    calls = []

    def fetch(url: str) -> str:
        calls.append(url)
        return "{}"

    geo = _geocoder(fetch)
    assert geo.reverse(37.5, 127.0) is None
    assert geo.reverse(37.5, 127.0) is None
    assert len(calls) == 1


def test_upstream_throttle_one_per_second():
    """캐시 미스 연속 호출 사이에 min_interval 만큼 sleep 한다(Nominatim 1 req/s)."""
    sleeps = []
    clock = FakeClock()

    geo = NominatimGeocoder(
        fetch=lambda url: SEARCH_BODY,
        clock=clock,
        sleep=lambda s: sleeps.append(s),
        min_interval_s=1.0,
    )
    geo.search("쿼리1")
    geo.search("쿼리2")  # 다른 키 → 캐시 미스 → 스로틀 대기
    assert len(sleeps) == 1
    assert sleeps[0] == 1.0


def test_upstream_error_degrades_to_empty():
    def fetch(url: str) -> str:
        raise OSError("connection refused")

    geo = _geocoder(fetch)
    assert geo.search("강남") == []
    assert geo.reverse(37.5, 127.0) is None


def test_search_viewbox_passed_to_upstream():
    seen = []

    def fetch(url: str) -> str:
        seen.append(url)
        return "[]"

    geo = _geocoder(fetch)
    geo.search("강남", viewbox=(126.76, 37.41, 127.18, 37.7))
    assert "viewbox=126.76%2C37.41%2C127.18%2C37.7" in seen[0]
    assert "bounded=1" in seen[0]


# ----------------------------------------------------------------------
# 엔드포인트
# ----------------------------------------------------------------------


def _client_with_fake(fetch) -> TestClient:
    set_geocoder(_geocoder(fetch))
    return TestClient(create_app())


def test_endpoint_search():
    client = _client_with_fake(lambda url: SEARCH_BODY)
    resp = client.get("/v1/geocode/search", params={"q": "강남구청"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["results"]) == 2
    assert body["results"][0]["name"] == "강남구청"
    assert body["results"][0]["lat"] == 37.4975


def test_endpoint_search_validation():
    client = _client_with_fake(lambda url: SEARCH_BODY)
    assert client.get("/v1/geocode/search").status_code == 422  # q 누락
    assert client.get("/v1/geocode/search", params={"q": ""}).status_code == 422
    assert (
        client.get("/v1/geocode/search", params={"q": "강남", "viewbox": "1,2,3"}).status_code
        == 422
    )  # viewbox 원소 부족
    assert (
        client.get("/v1/geocode/search", params={"q": "강남", "limit": 100}).status_code == 422
    )  # limit 상한 초과


def test_endpoint_reverse():
    client = _client_with_fake(lambda url: REVERSE_BODY)
    resp = client.get("/v1/geocode/reverse", params={"lat": 37.4975, "lon": 127.027})
    assert resp.status_code == 200
    assert resp.json()["label"].startswith("강남구청")


def test_endpoint_reverse_validation():
    client = _client_with_fake(lambda url: REVERSE_BODY)
    assert client.get("/v1/geocode/reverse", params={"lat": 91, "lon": 0}).status_code == 422
    assert client.get("/v1/geocode/reverse", params={"lat": 0}).status_code == 422  # lon 누락


def test_endpoint_upstream_down_returns_empty_200():
    """업스트림 장애는 200 + 빈 결과 — 검색 UI 가 '결과 없음'으로 처리."""

    def fetch(url: str) -> str:
        raise OSError("down")

    client = _client_with_fake(fetch)
    resp = client.get("/v1/geocode/search", params={"q": "강남"})
    assert resp.status_code == 200
    assert resp.json()["results"] == []
    resp = client.get("/v1/geocode/reverse", params={"lat": 37.5, "lon": 127.0})
    assert resp.status_code == 200
    assert resp.json()["label"] is None
