"""경로 탐색 제공자(Directions Provider).

MVP 는 외부 지도 API(카카오/네이버)에서 도보 경로 좌표를 받는다. 약관/키 없이도
동작·테스트할 수 있도록 직선 보간 제공자(StraightLineProvider)를 기본 제공하고,
카카오 제공자는 키가 있을 때만 사용한다.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Protocol

from .config import Settings
from .models import LatLng


class DirectionsProvider(Protocol):
    name: str

    def route(self, origin: LatLng, destination: LatLng, mode: str) -> list[LatLng]:
        """출발→도착 경로 폴리라인(위경도 리스트)을 반환."""
        ...


class StraightLineProvider:
    """출발→도착을 직선으로 균등 보간(오프라인/테스트용 기본 제공자).

    실제 길찾기가 아니라 그늘 엔진 파이프라인 검증용. 약 step_m 간격으로 점을 만든다.
    """

    name = "straight"

    def __init__(self, step_m: float = 25.0) -> None:
        self.step_m = step_m

    def route(self, origin: LatLng, destination: LatLng, mode: str) -> list[LatLng]:
        from shade_engine.geo import haversine_m  # 지연 import (sys.path 설정 후)

        dist = haversine_m(origin.lat, origin.lon, destination.lat, destination.lon)
        n = max(1, int(dist // self.step_m))
        pts = [
            LatLng(
                lat=origin.lat + (destination.lat - origin.lat) * i / n,
                lon=origin.lon + (destination.lon - origin.lon) * i / n,
            )
            for i in range(n + 1)
        ]
        return pts


class KakaoDirectionsProvider:
    """카카오모빌리티 도보 길찾기. REST API 키 필요.

    NOTE: 실제 엔드포인트/응답 스키마는 약관·계약에 따라 다르므로, 운영 전 §8 약관
    검토(그림자 오버레이 허용 여부 포함)와 함께 확정한다. 여기서는 표준 응답
    (sections[].roads[].vertexes 평면 좌표열)을 가정해 파싱한다.
    """

    name = "kakao"
    _ENDPOINT = "https://apis-navi.kakaomobility.com/v1/directions"

    def __init__(self, api_key: str, timeout: float = 10.0) -> None:
        if not api_key:
            raise ValueError("Kakao REST API 키가 필요합니다.")
        self.api_key = api_key
        self.timeout = timeout

    def route(self, origin: LatLng, destination: LatLng, mode: str) -> list[LatLng]:
        params = urllib.parse.urlencode(
            {
                "origin": f"{origin.lon},{origin.lat}",
                "destination": f"{destination.lon},{destination.lat}",
                "priority": "RECOMMEND",
            }
        )
        req = urllib.request.Request(
            f"{self._ENDPOINT}?{params}",
            headers={"Authorization": f"KakaoAK {self.api_key}"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
            payload = json.loads(resp.read().decode("utf-8"))
        return self._parse(payload)

    @staticmethod
    def _parse(payload: dict) -> list[LatLng]:
        pts: list[LatLng] = []
        for route in payload.get("routes", []):
            for section in route.get("sections", []):
                for road in section.get("roads", []):
                    vx = road.get("vertexes", [])
                    # vertexes 는 [lon, lat, lon, lat, ...] 평면 배열
                    for i in range(0, len(vx) - 1, 2):
                        pts.append(LatLng(lon=float(vx[i]), lat=float(vx[i + 1])))
        return pts


def get_provider(settings: Settings) -> DirectionsProvider:
    if settings.directions_provider == "kakao" and settings.kakao_rest_api_key:
        return KakaoDirectionsProvider(settings.kakao_rest_api_key)
    return StraightLineProvider()
