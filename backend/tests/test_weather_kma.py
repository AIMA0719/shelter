"""기상청(KMA) 날씨 제공자 단위 테스트.

네트워크 호출 없이 순수 함수와 클래스 인터페이스를 검증한다.
"""

from __future__ import annotations

import os

import pytest

from app.weather import (
    KMAWeatherProvider,
    StubWeatherProvider,
    _parse_ultra_srt_ncst,
    get_weather_provider,
    latlon_to_grid,
)


# ---------------------------------------------------------------------------
# latlon_to_grid — Lambert Conformal Conic 좌표 변환
# ---------------------------------------------------------------------------


def test_latlon_to_grid_seoul():
    """서울 좌표(37.5665, 126.9780)는 기상청 격자 (60, 127) 로 변환되어야 한다."""
    nx, ny = latlon_to_grid(37.5665, 126.9780)
    assert nx == 60
    assert ny == 127


# ---------------------------------------------------------------------------
# _parse_ultra_srt_ncst — JSON 파서
# ---------------------------------------------------------------------------

_SAMPLE_PAYLOAD = {
    "response": {
        "header": {"resultCode": "00", "resultMsg": "NORMAL_SERVICE"},
        "body": {
            "dataType": "JSON",
            "items": {
                "item": [
                    {"category": "PTY", "obsrValue": "0"},
                    {"category": "REH", "obsrValue": "60"},
                    {"category": "RN1", "obsrValue": "0"},
                    {"category": "T1H", "obsrValue": "28.5"},
                    {"category": "UUU", "obsrValue": "1.2"},
                    {"category": "VEC", "obsrValue": "180"},
                    {"category": "VVV", "obsrValue": "-0.8"},
                    {"category": "WSD", "obsrValue": "1.4"},
                ]
            },
            "pageNo": 1,
            "numOfRows": 10,
            "totalCount": 8,
        },
    }
}


def test_parse_ultra_srt_ncst_returns_temp():
    """T1H 항목이 있는 정상 응답에서 기온 28.5를 반환해야 한다."""
    temp = _parse_ultra_srt_ncst(_SAMPLE_PAYLOAD)
    assert temp == 28.5


def test_parse_ultra_srt_ncst_empty_payload():
    """비어있는/형식이 잘못된 payload 에서는 None 을 반환해야 한다."""
    assert _parse_ultra_srt_ncst({}) is None
    assert _parse_ultra_srt_ncst(None) is None
    assert _parse_ultra_srt_ncst({"response": {}}) is None
    assert _parse_ultra_srt_ncst("garbage") is None


def test_parse_ultra_srt_ncst_no_t1h():
    """T1H 항목이 없는 응답에서는 None 을 반환해야 한다."""
    payload = {
        "response": {
            "body": {
                "items": {
                    "item": [
                        {"category": "PTY", "obsrValue": "0"},
                        {"category": "REH", "obsrValue": "60"},
                    ]
                }
            }
        }
    }
    assert _parse_ultra_srt_ncst(payload) is None


# ---------------------------------------------------------------------------
# get_weather_provider — 키 유무에 따른 제공자 선택
# ---------------------------------------------------------------------------


def test_get_weather_provider_no_key_returns_stub(monkeypatch):
    """SHELTER_KMA_SERVICE_KEY 가 없으면 StubWeatherProvider 를 반환해야 한다."""
    monkeypatch.delenv("SHELTER_KMA_SERVICE_KEY", raising=False)
    provider = get_weather_provider()
    assert isinstance(provider, StubWeatherProvider)


def test_get_weather_provider_with_key_returns_kma(monkeypatch):
    """SHELTER_KMA_SERVICE_KEY 가 설정되면 KMAWeatherProvider 를 반환해야 한다."""
    monkeypatch.setenv("SHELTER_KMA_SERVICE_KEY", "test-dummy-key-12345")
    provider = get_weather_provider()
    assert isinstance(provider, KMAWeatherProvider)
    assert provider.name == "kma"


# ---------------------------------------------------------------------------
# KMAWeatherProvider — 직접 생성 시 name 속성 확인
# ---------------------------------------------------------------------------


def test_kma_provider_name():
    """KMAWeatherProvider 인스턴스의 name 속성은 'kma' 여야 한다."""
    provider = KMAWeatherProvider("dummy-key")
    assert provider.name == "kma"


def test_kma_provider_requires_key():
    """빈 키로 KMAWeatherProvider 를 생성하면 ValueError 가 발생해야 한다."""
    with pytest.raises(ValueError, match="KMA 서비스 키"):
        KMAWeatherProvider("")


def test_kma_future_departure_falls_back_to_stub():
    """코덱스 회귀: 미래 출발시각은 관측이 없으므로 stub 으로 폴백(네트워크 미사용)."""
    from datetime import datetime, timedelta, timezone

    provider = KMAWeatherProvider("dummy-key")
    future = datetime.now(timezone.utc) + timedelta(days=1)  # 내일 → 관측 불가
    info = provider.badge(37.5665, 126.9780, future)
    assert info.source == "stub"  # KMA 관측 대신 stub 사용
    assert info.temp_c is not None
