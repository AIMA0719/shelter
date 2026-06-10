"""클라이언트 IP 단위 고정창(fixed-window) 레이트리미터.

운영에서 단일 IP 의 과도한 요청을 막는다. 분산 환경에서는 Redis 기반으로 교체하되,
인터페이스(allow)는 동일하게 유지한다. 스레드 안전.
"""

from __future__ import annotations

import threading


class RateLimiter:
    def __init__(self, limit_per_min: int) -> None:
        self.limit = limit_per_min
        self._lock = threading.Lock()
        self._window: dict[str, tuple[int, int]] = {}  # key -> (창 시작(분), 카운트)
        self._last_minute = -1  # 마지막으로 청소한 분

    def allow(self, key: str, now_seconds: float) -> bool:
        """이번 요청을 허용하면 True, 한도 초과면 False."""
        if self.limit <= 0:
            return True
        minute = int(now_seconds // 60)
        with self._lock:
            # 분이 바뀌면 지난 창의 키를 모두 제거한다. 이렇게 하지 않으면 한 번
            # 본 IP 가 영구히 dict 에 남아 메모리가 무한히 증가한다(키 누수).
            if minute != self._last_minute:
                self._window = {
                    k: v for k, v in self._window.items() if v[0] == minute
                }
                self._last_minute = minute
            start, count = self._window.get(key, (minute, 0))
            if start != minute:
                start, count = minute, 0
            count += 1
            self._window[key] = (start, count)
            return count <= self.limit
