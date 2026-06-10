"""API 요청/응답 스키마 (pydantic v2)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

TravelMode = Literal["walk", "bike"]  # Phase 2: 자전거 모드 추가

# 모드별 평균 속도(m/s). 이동 중 태양 이동 계산에 사용.
MODE_SPEED_MPS: dict[str, float] = {"walk": 1.3, "bike": 4.2}


class LatLng(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class ShadeRequest(BaseModel):
    """출발/도착(또는 명시 경로) + 출발 시각 + 모드.

    origin/destination 으로 경로를 자동 탐색하거나, coords 로 경로를 직접 지정한다.
    """

    origin: LatLng | None = None
    destination: LatLng | None = None
    coords: list[LatLng] | None = Field(default=None, description="명시 경로(있으면 directions 생략)")
    depart_time: datetime | None = Field(default=None, description="출발 시각(tz 포함 권장, 미지정 시 서버 now)")
    mode: TravelMode = "walk"
    spacing_m: float = Field(default=10.0, gt=0, le=100)
    moving_sun: bool = True

    @model_validator(mode="after")
    def _check_route_inputs(self) -> ShadeRequest:
        has_od = self.origin is not None and self.destination is not None
        has_coords = self.coords is not None and len(self.coords) >= 2
        if not has_od and not has_coords:
            raise ValueError("origin+destination 또는 coords(2점 이상) 중 하나는 필요합니다.")
        return self


class SegmentOut(BaseModel):
    """경로의 한 구간(샘플 a→b)과 그늘 여부."""

    a: LatLng
    b: LatLng
    shaded: bool
    reason: str
    confidence: float


class ShadeResponse(BaseModel):
    shade_percent: float
    total_distance_m: float
    sample_count: int
    mean_confidence: float
    depart_time: datetime
    mode: TravelMode
    provider: str
    building_count: int
    cached: bool = False
    segments: list[SegmentOut]


class WeatherBadge(BaseModel):
    temp_c: float | None = None
    uv_index: float | None = None
    heat_advisory: bool = False
    source: str


RoutePreference = Literal["shade", "sun"]  # shade=여름(기본), sun=겨울 햇빛 모드


class RoutesRequest(BaseModel):
    """경로 추천: 출발/도착 필수(격자 라우팅)."""

    origin: LatLng
    destination: LatLng
    depart_time: datetime | None = None
    mode: TravelMode = "walk"
    grid_spacing_m: float = Field(default=20.0, gt=2, le=100)
    prefer: RoutePreference = "shade"


class RouteOptionOut(BaseModel):
    name: str  # 'shortest' | 'balanced' | 'shadiest' | 'sunniest'
    distance_m: float
    duration_min: float  # 모드 평균속도 기준 예상 소요시간(분) — P0 비교축(거리·시간·그늘%)
    shade_percent: float
    comfort: float
    coords: list[LatLng]
    segments: list[SegmentOut]


class RoutesResponse(BaseModel):
    depart_time: datetime
    mode: TravelMode
    prefer: RoutePreference
    routing: str  # 'osm'(실제 보행 그래프) | 'grid'(격자 프로토타입)
    building_count: int
    cached: bool = False
    weather: WeatherBadge | None = None
    options: list[RouteOptionOut]


class DepartureSuggestRequest(BaseModel):
    origin: LatLng
    destination: LatLng
    date: str | None = Field(default=None, description="YYYY-MM-DD (미지정 시 오늘)")
    hours: list[int] | None = Field(default=None, description="후보 출발 시(0~23). 기본 8~18")
    mode: TravelMode = "walk"
    prefer: RoutePreference = "shade"


class DepartureCandidateOut(BaseModel):
    depart_time: datetime
    shade_percent: float


class DepartureSuggestResponse(BaseModel):
    best: DepartureCandidateOut
    prefer: RoutePreference
    candidates: list[DepartureCandidateOut]


class Poi(BaseModel):
    lat: float
    lon: float
    type: str  # 'shade_shelter' | 'cooling_center' | 'water_fountain'
    name: str | None = None


class PoisResponse(BaseModel):
    pois: list[Poi]


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    buildings_loaded: int
