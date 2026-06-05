"""경로 그늘 결과 캐시 (LRU).

동일한 경로·날짜·시각대 요청은 재계산이 낭비이므로 결과를 캐싱한다. 키는
(경로 서명, 날짜, 시각대, 모드, 간격)으로 구성한다. 운영에서는 타일 단위 캐시로
확장하지만 MVP 는 경로 단위 LRU 로 충분하다.
"""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from datetime import datetime

from .models import LatLng


def route_cache_key(
    coords: list[LatLng], depart: datetime, mode: str, spacing_m: float, moving_sun: bool
) -> str:
    """경로 좌표(약 11m 격자로 라운딩) + 날짜 + 시각대(시) 기반 캐시 키."""
    # 1e-4도 ≈ 11m 로 라운딩해 미세한 좌표 차이를 같은 키로 묶는다.
    coord_sig = ";".join(f"{round(p.lat, 4)},{round(p.lon, 4)}" for p in coords)
    digest = hashlib.sha1(coord_sig.encode("utf-8")).hexdigest()[:16]
    date_bucket = depart.strftime("%Y%m%d")
    hour_bucket = depart.hour
    return f"{digest}|{date_bucket}|{hour_bucket}|{mode}|{spacing_m}|{int(moving_sun)}"


class LRUCache:
    """간단한 크기 제한 LRU 캐시."""

    def __init__(self, max_entries: int = 512) -> None:
        self.max_entries = max_entries
        self._store: OrderedDict[str, object] = OrderedDict()

    def get(self, key: str) -> object | None:
        if key not in self._store:
            return None
        self._store.move_to_end(key)
        return self._store[key]

    def set(self, key: str, value: object) -> None:
        self._store[key] = value
        self._store.move_to_end(key)
        while len(self._store) > self.max_entries:
            self._store.popitem(last=False)

    def clear(self) -> None:
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)
