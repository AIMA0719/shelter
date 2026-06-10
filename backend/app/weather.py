"""기상 배지 제공자 (Phase 2).

자외선지수·기온·폭염특보를 경로 화면에 배지로 표시한다. 운영은 기상청(KMA) API 를
쓰되 키가 필요하므로, 키 없이도 동작하도록 계절/시각 기반 추정 스텁을 기본 제공한다.
"""

from __future__ import annotations

import json
import math
import urllib.parse
import urllib.request
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Any
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


# ---------------------------------------------------------------------------
# KMA Lambert Conformal Conic (DFS) 좌표 변환 상수
# 기상청 공식 문서의 격자 변환 파라미터를 그대로 사용한다.
# ---------------------------------------------------------------------------
_RE = 6371.00877        # 지구 반경(km)
_GRID = 5.0             # 격자 간격(km)
_SLAT1 = 30.0           # 투영 위도 1(도)
_SLAT2 = 60.0           # 투영 위도 2(도)
_OLON = 126.0           # 기준점 경도(도)
_OLAT = 38.0            # 기준점 위도(도)
_XO = 43.0              # 기준점 X 좌표(격자)
_YO = 136.0             # 기준점 Y 좌표(격자)
_DEGRAD = math.pi / 180.0


def latlon_to_grid(lat: float, lon: float) -> tuple[int, int]:
    """위경도(WGS-84)를 기상청 격자 좌표(nx, ny)로 변환한다.

    기상청 공식 DFS Lambert Conformal Conic 투영 공식을 그대로 구현.
    서울(37.5665, 126.9780) → (60, 127) 을 기준으로 검증한다.
    """
    re = _RE / _GRID
    slat1 = _SLAT1 * _DEGRAD
    slat2 = _SLAT2 * _DEGRAD
    olon = _OLON * _DEGRAD
    olat = _OLAT * _DEGRAD

    sn = math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(sn)
    sf = math.tan(math.pi * 0.25 + slat1 * 0.5)
    sf = (sf ** sn) * math.cos(slat1) / sn
    ro = math.tan(math.pi * 0.25 + olat * 0.5)
    ro = re * sf / (ro ** sn)

    ra = math.tan(math.pi * 0.25 + lat * _DEGRAD * 0.5)
    ra = re * sf / (ra ** sn)
    theta = lon * _DEGRAD - olon
    if theta > math.pi:
        theta -= 2.0 * math.pi
    if theta < -math.pi:
        theta += 2.0 * math.pi
    theta *= sn

    nx = int(ra * math.sin(theta) + _XO + 0.5)
    ny = int(ro - ra * math.cos(theta) + _YO + 0.5)
    return nx, ny


def _parse_ultra_srt_ncst(payload: Any) -> float | None:
    """기상청 초단기실황(getUltraSrtNcst) JSON 응답에서 기온(T1H, °C)을 추출한다.

    응답 구조: payload["response"]["body"]["items"]["item"] = list[{category, obsrValue, ...}]
    T1H 항목이 없거나 형식이 잘못되면 None 을 반환한다.
    """
    try:
        items = payload["response"]["body"]["items"]["item"]
        for item in items:
            if item.get("category") == "T1H":
                return float(item["obsrValue"])
    except (KeyError, TypeError, ValueError):
        pass
    return None


_KMA_ENDPOINT = (
    "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst"
)
_KST = timezone(timedelta(hours=9))


def _base_date_time(now_kst: datetime) -> tuple[str, str]:
    """현재(KST) 기준 가장 최근에 제공되는 초단기실황 발표일자/시각.

    매시각 정시 생성 + '매시각 10분 이후' 제공이므로, 정시 후 10분이 안 됐으면
    직전 시각을 쓴다. 관측은 '현재' 기준이어야 한다(요청 출발시각이 아니라).
    """
    t = now_kst
    if t.minute < 10:
        t = t - timedelta(hours=1)
    return t.strftime("%Y%m%d"), t.strftime("%H00")


class KMAWeatherProvider:
    """기상청(KMA) 초단기실황 API 를 사용한 실시간 기상 제공자.

    서비스 키(SHELTER_KMA_SERVICE_KEY)가 있을 때 get_weather_provider() 가 반환한다.
    네트워크/파싱 오류 시 StubWeatherProvider 로 자동 폴백해 엔드포인트를 보호한다.

    NOTE: 자외선 지수(uv_index)는 별도 API(기상청 자외선 지수 조회)가 필요하므로
    이 구현에서는 None 으로 반환한다. 추후 areaNo 기반 API 연동 시 채울 수 있다.
    """

    name = "kma"

    def __init__(self, service_key: str, timeout: float = 10.0) -> None:
        if not service_key:
            raise ValueError("KMA 서비스 키가 필요합니다.")
        self._key = service_key
        self._timeout = timeout
        self._stub = StubWeatherProvider()

    def badge(self, lat: float, lon: float, dt: datetime) -> WeatherInfo:
        # 초단기실황은 '관측'이라 현재 시각대만 유효하다. 미래/먼 과거 출발시각은
        # 관측이 없어 temp=null 이 되므로, 그 경우 계절/시각 추정 stub 으로 폴백한다.
        dt_utc = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
        delta = (dt_utc - datetime.now(timezone.utc)).total_seconds()
        if delta > 900 or delta < -7200:  # 미래 15분 초과 또는 과거 2시간 초과
            return self._stub.badge(lat, lon, dt)
        try:
            info = self._fetch(lat, lon, dt)
        except Exception:  # noqa: BLE001
            return self._stub.badge(lat, lon, dt)
        # 관측값이 없으면(temp 없음) stub 으로 폴백 — null 배지 반환 금지.
        if info.temp_c is None:
            return self._stub.badge(lat, lon, dt)
        # UV 는 별도 API 미연동이라 실황엔 없다. 그대로 두면 comfort 의 최대 가중항
        # (uv*3)이 통째로 사라져 쾌적도가 체계적으로 과대평가된다. 실측 기온은 살리되,
        # UV 는 계절/시각 추정(stub)으로 채운다 — null 배지/누락 가중치 방지.
        if info.uv_index is None:
            info = replace(info, uv_index=self._stub.badge(lat, lon, dt).uv_index)
        return info

    def _fetch(self, lat: float, lon: float, dt: datetime) -> WeatherInfo:
        nx, ny = latlon_to_grid(lat, lon)

        # 초단기실황은 '현재 관측'이므로 요청 출발시각(dt)이 아니라 현재 시각 기준으로
        # 가장 최근 발표분을 조회한다(근미래 출발이 다음 시각으로 넘어가 미제공 관측을
        # 조회하던 문제 방지).
        base_date, base_time = _base_date_time(datetime.now(_KST))

        params = urllib.parse.urlencode(
            {
                "serviceKey": self._key,
                "base_date": base_date,
                "base_time": base_time,
                "nx": nx,
                "ny": ny,
                "numOfRows": 10,
                "pageNo": 1,
                "dataType": "JSON",
            }
        )
        url = f"{_KMA_ENDPOINT}?{params}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:  # noqa: S310
            payload = json.loads(resp.read().decode("utf-8"))

        temp = _parse_ultra_srt_ncst(payload)
        return WeatherInfo(
            temp_c=temp,
            uv_index=None,  # UV 는 별도 areaNo API — 현재 범위 외
            heat_advisory=(temp is not None and temp >= 33.0),
            source=self.name,
        )


def get_weather_provider() -> WeatherProvider:
    """설정(SHELTER_KMA_SERVICE_KEY)에 따라 적절한 날씨 제공자를 반환한다.

    키가 설정되어 있으면 KMAWeatherProvider, 아니면 StubWeatherProvider 를 반환한다.

    NOTE: os.getenv 를 직접 호출해 환경 변수를 매번 새로 읽는다.
    config.Settings 의 기본값은 모듈 임포트 시 고정되므로, 테스트에서
    monkeypatch 로 환경변수를 바꾸더라도 Settings() 를 경유하면 반영이 안 된다.
    """
    import os

    key = os.getenv("SHELTER_KMA_SERVICE_KEY", "")
    if key:
        return KMAWeatherProvider(key)
    return StubWeatherProvider()
