"""체감 쾌적도 점수 (Phase 3 기초).

그늘 비율 + 기온 + 자외선으로 0~100 의 쾌적도 점수를 만든다(높을수록 쾌적).
더울수록·자외선이 셀수록 '햇빛 노출'의 페널티가 커진다. 비전 "날씨를 피하는
길찾기"의 첫 단계 — 추후 바람·습도·미세먼지를 추가한다.
"""

from __future__ import annotations

_BASE_SUN_PENALTY = 10.0  # 더위와 무관한 기본 햇빛 페널티
_NEUTRAL_TEMP_C = 22.0  # 이 온도 이하에서는 더위 페널티 없음


def comfort_score(
    shade_fraction: float, temp_c: float | None = None, uv_index: float | None = None
) -> float:
    """쾌적도 0~100. 그늘이 많을수록·덜 더울수록·자외선이 약할수록 높다."""
    shade = min(max(shade_fraction, 0.0), 1.0)
    sun_fraction = 1.0 - shade
    heat_excess = 0.0 if temp_c is None else max(0.0, temp_c - _NEUTRAL_TEMP_C)
    uv = uv_index or 0.0
    penalty = sun_fraction * (_BASE_SUN_PENALTY + heat_excess * 2.0 + uv * 3.0)
    return round(max(0.0, 100.0 - penalty), 1)
