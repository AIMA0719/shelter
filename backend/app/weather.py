"""기상 배지 제공자 (Phase 2).

자외선지수·기온·폭염특보를 경로 화면에 배지로 표시한다. 운영은 기상청(KMA) API 를
쓰되 키가 필요하므로, 키 없이도 동작하도록 계절/시각 기반 추정 스텁을 기본 제공한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class WeatherInfo:
    temp_c: float | None
    uv_index: float | None
    heat_advisory: bool
    source: str


class WeatherProvider(Protocol):
    def badge(self, lat: float, lon: float, dt: datetime) -> WeatherInfo:
        ...


class StubWeatherProvider:
    """계절/시각 기반 간이 추정(키 불필요). 실데이터 아님, UX/통합 검증용."""

    name = "stub"

    def badge(self, lat: float, lon: float, dt: datetime) -> WeatherInfo:
        month = dt.month
        hour = dt.hour
        is_summer = month in (6, 7, 8)
        # 한낮일수록 기온·자외선 상승(아주 단순한 모델)
        midday_factor = max(0.0, 1.0 - abs(hour - 14) / 9.0)
        if is_summer:
            temp = 26.0 + 9.0 * midday_factor  # 26~35도
            uv = round(2.0 + 9.0 * midday_factor, 1)  # 2~11
        else:
            temp = 8.0 + 10.0 * midday_factor
            uv = round(1.0 + 4.0 * midday_factor, 1)
        return WeatherInfo(
            temp_c=round(temp, 1),
            uv_index=uv,
            heat_advisory=temp >= 33.0,  # 폭염주의보 기준 근사
            source=self.name,
        )


def get_weather_provider() -> WeatherProvider:
    # 키 연동 시 KMAWeatherProvider 로 교체.
    return StubWeatherProvider()
