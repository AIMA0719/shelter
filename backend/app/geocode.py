"""지오코딩 프록시 (OSM Nominatim).

앱이 Nominatim 을 직접 호출하면 사용자 수만큼의 IP 에서 동일 User-Agent 로
요청이 흩어져 ToS(1 req/s, 유효 UA, 캐싱 권장) 준수를 보장할 수 없고 밴 위험이
있다. 백엔드가 단일 출구로 프록시하면서 다음을 보장한다:

  1. 유효한 User-Agent + 연락처 (Nominatim 필수 요건)
  2. 업스트림 호출 1 req/s 스로틀 (전역 락 — 프로세스 단일 출구)
  3. TTL+LRU 캐시 (지오코딩 결과는 사실상 정적 → 반복 질의는 업스트림 미호출)

업스트림 오류는 빈 결과로 강등한다(날씨 stub 폴백과 같은 원칙 — 검색 실패가
앱 흐름을 깨지 않도록). 검색 UI 는 빈 리스트를 '결과 없음'으로 처리한다.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.parse
import urllib.request
from collections import OrderedDict

from .models import GeocodePlace

_DEFAULT_BASE_URL = "https://nominatim.openstreetmap.org"


class NominatimGeocoder:
    """Nominatim 검색/역지오코딩 클라이언트 (캐시 + 스로틀 내장).

    테스트는 ``fetch``(URL→응답 본문 str)를 주입해 네트워크 없이 검증한다.
    ``clock``/``sleep`` 도 주입 가능(스로틀 검증용).
    """

    def __init__(
        self,
        base_url: str = _DEFAULT_BASE_URL,
        user_agent: str = "shelter-shade-backend/0.1 (contact: tech.infocar@gmail.com)",
        timeout: float = 10.0,
        cache_max_entries: int = 512,
        cache_ttl_s: float = 24 * 3600.0,
        min_interval_s: float = 1.0,
        fetch=None,  # type: ignore[no-untyped-def]
        clock=time.monotonic,  # type: ignore[no-untyped-def]
        sleep=time.sleep,  # type: ignore[no-untyped-def]
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._user_agent = user_agent
        self._timeout = timeout
        self._fetch = fetch or self._http_get
        self._clock = clock
        self._sleep = sleep

        # TTL+LRU 캐시. 값은 (만료 시각, 결과). 지오코딩 결과는 거의 변하지 않아
        # 긴 TTL(기본 24h)로 업스트림 호출을 대부분 제거한다.
        self._cache: OrderedDict[str, tuple[float, object]] = OrderedDict()
        self._cache_max = cache_max_entries
        self._cache_ttl = cache_ttl_s
        self._cache_lock = threading.Lock()

        # 업스트림 스로틀: Nominatim ToS 의 1 req/s 를 프로세스 전역으로 보장.
        # FastAPI 동기 핸들러는 스레드풀에서 돌므로 락 + 마지막 호출 시각으로 직렬화.
        # 캐시 적중이 대부분이라 대기 행렬이 길어질 일은 드물다.
        self._throttle_lock = threading.Lock()
        self._min_interval = min_interval_s
        self._last_call = -min_interval_s  # 첫 호출은 대기 없음

    # ------------------------------------------------------------------
    # 공개 API
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        viewbox: tuple[float, float, float, float] | None = None,
        limit: int = 8,
    ) -> list[GeocodePlace]:
        """검색어 → 장소 목록. 업스트림 오류 시 빈 리스트."""
        params: dict[str, object] = {
            "q": query,
            "format": "jsonv2",
            "limit": limit,
            "addressdetails": 1,
            "accept-language": "ko",
        }
        if viewbox is not None:
            # viewbox = (minLon, minLat, maxLon, maxLat), bounded=1 → 박스 내 한정
            params["viewbox"] = ",".join(f"{v}" for v in viewbox)
            params["bounded"] = 1

        url = f"{self._base_url}/search?{urllib.parse.urlencode(params)}"
        cached = self._cache_get(url)
        if cached is not None:
            return cached  # type: ignore[return-value]

        try:
            body = self._fetch_throttled(url)
            results = parse_search_results(body)
        except Exception:  # noqa: BLE001 — 업스트림 오류는 빈 결과로 강등
            return []
        self._cache_set(url, results)
        return results

    def reverse(self, lat: float, lon: float) -> str | None:
        """좌표 → 사람이 읽는 라벨(display_name). 실패 시 None."""
        # 1e-5도 ≈ 1.1m 라운딩 — 지도 롱프레스의 미세 좌표 차이를 같은 키로 묶는다.
        params = urllib.parse.urlencode(
            {
                "lat": round(lat, 5),
                "lon": round(lon, 5),
                "format": "jsonv2",
                "accept-language": "ko",
                "zoom": 18,
            }
        )
        url = f"{self._base_url}/reverse?{params}"
        cached = self._cache_get(url)
        if cached is not None:
            return cached or None  # 캐시된 '결과 없음'은 빈 문자열로 저장됨

        try:
            body = self._fetch_throttled(url)
            label = parse_reverse(body)
        except Exception:  # noqa: BLE001
            return None
        # None 도 캐시해야 같은 좌표 반복 호출이 업스트림을 때리지 않는다.
        self._cache_set(url, label or "")
        return label

    # ------------------------------------------------------------------
    # 내부: 캐시 / 스로틀 / HTTP
    # ------------------------------------------------------------------

    def _cache_get(self, key: str) -> object | None:
        with self._cache_lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            expires, value = entry
            if self._clock() >= expires:
                del self._cache[key]
                return None
            self._cache.move_to_end(key)
            return value

    def _cache_set(self, key: str, value: object) -> None:
        with self._cache_lock:
            self._cache[key] = (self._clock() + self._cache_ttl, value)
            self._cache.move_to_end(key)
            while len(self._cache) > self._cache_max:
                self._cache.popitem(last=False)

    def _fetch_throttled(self, url: str) -> str:
        with self._throttle_lock:
            wait = self._min_interval - (self._clock() - self._last_call)
            if wait > 0:
                self._sleep(wait)
            self._last_call = self._clock()
        return self._fetch(url)

    def _http_get(self, url: str) -> str:
        req = urllib.request.Request(url, headers={"User-Agent": self._user_agent})
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:  # noqa: S310
            return resp.read().decode("utf-8")


# ----------------------------------------------------------------------
# 응답 파싱 (앱의 기존 PlaceSearch 파서와 동일한 규칙 — 서버로 이전)
# ----------------------------------------------------------------------


def parse_search_results(body: str) -> list[GeocodePlace]:
    """Nominatim jsonv2 search 응답(JSON 배열) → GeocodePlace 목록.

    - lat/lon 은 문자열로 와서 float 변환.
    - name 이 비어 있으면 display_name 의 첫 쉼표 구간을 이름으로 사용.
    - 손상된 원소는 조용히 건너뛴다.
    """
    try:
        root = json.loads(body)
    except (ValueError, TypeError):
        return []
    if not isinstance(root, list):
        return []

    results: list[GeocodePlace] = []
    for element in root:
        if not isinstance(element, dict):
            continue
        try:
            lat = float(element["lat"])
            lon = float(element["lon"])
        except (KeyError, ValueError, TypeError):
            continue
        display_name = element.get("display_name")
        display_name = display_name if isinstance(display_name, str) else None
        raw_name = element.get("name")
        if isinstance(raw_name, str) and raw_name.strip():
            name = raw_name
        elif display_name:
            name = display_name.split(",")[0].strip() or display_name
        else:
            continue
        results.append(GeocodePlace(name=name, lat=lat, lon=lon, address=display_name))
    return results


def parse_reverse(body: str) -> str | None:
    """Nominatim jsonv2 reverse 응답(JSON 객체)의 display_name. 없으면 None."""
    try:
        root = json.loads(body)
    except (ValueError, TypeError):
        return None
    if not isinstance(root, dict):
        return None
    name = root.get("display_name")
    return name if isinstance(name, str) and name else None
