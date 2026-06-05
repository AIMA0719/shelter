"""경로 그늘 결과 캐시 (LRU).

동일한 경로·날짜·시각대 요청은 재계산이 낭비이므로 결과를 캐싱한다. 키는
(경로 서명, 날짜, 시각대, 모드, 간격)으로 구성한다. 운영에서는 타일 단위 캐시로
확장하지만 MVP 는 경로 단위 LRU 로 충분하다.
"""

from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict
from datetime import datetime, timezone

from .models import LatLng


def route_cache_key(
    coords: list[LatLng], depart: datetime, mode: str, spacing_m: float, moving_sun: bool
) -> str:
    """경로 좌표(약 11m 격자로 라운딩) + 출발 시각(UTC 정규화·분 단위) 기반 캐시 키.

    그늘은 출발 시각에 연속적으로 의존하므로 시(hour) 단위 버킷은 같은 시간대의 다른
    시각(또는 다른 타임존)을 충돌시켜 잘못된 결과를 줄 수 있다. 타임존을 UTC 로
    정규화하고 분 단위까지 키에 포함해 충돌을 막는다(동일 요청은 그대로 캐시 적중).
    """
    # 1e-4도 ≈ 11m 로 라운딩해 미세한 좌표 차이를 같은 키로 묶는다.
    coord_sig = ";".join(f"{round(p.lat, 4)},{round(p.lon, 4)}" for p in coords)
    digest = hashlib.sha1(coord_sig.encode("utf-8")).hexdigest()[:16]
    depart_utc = (
        depart.replace(tzinfo=timezone.utc) if depart.tzinfo is None else depart.astimezone(timezone.utc)
    )
    instant = depart_utc.strftime("%Y%m%dT%H%M")  # UTC 분 단위
    return f"{digest}|{instant}|{mode}|{spacing_m}|{int(moving_sun)}"


def routes_cache_key(
    origin: LatLng,
    dest: LatLng,
    depart: datetime,
    mode: str,
    prefer: str,
    grid_spacing_m: float,
) -> str:
    """경로 추천(/v1/routes) 캐시 키. 출발/도착(11m 격자) + UTC 분 + 옵션."""
    depart_utc = (
        depart.replace(tzinfo=timezone.utc) if depart.tzinfo is None else depart.astimezone(timezone.utc)
    )
    instant = depart_utc.strftime("%Y%m%dT%H%M")
    return (
        f"routes|{round(origin.lat, 4)},{round(origin.lon, 4)}"
        f"|{round(dest.lat, 4)},{round(dest.lon, 4)}"
        f"|{instant}|{mode}|{prefer}|{grid_spacing_m}"
    )


class LRUCache:
    """크기 제한 LRU 캐시(스레드 안전).

    FastAPI 동기 핸들러는 스레드풀에서 동시 실행되므로 OrderedDict 접근을 락으로 보호한다.
    """

    def __init__(self, max_entries: int = 512) -> None:
        self.max_entries = max_entries
        self._store: OrderedDict[str, object] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> object | None:
        with self._lock:
            if key not in self._store:
                return None
            self._store.move_to_end(key)
            return self._store[key]

    def set(self, key: str, value: object) -> None:
        with self._lock:
            self._store[key] = value
            self._store.move_to_end(key)
            while len(self._store) > self.max_entries:
                self._store.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)
