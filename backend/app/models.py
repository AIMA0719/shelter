"""API 요청/응답 스키마 (pydantic v2)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

TravelMode = Literal["walk"]  # Phase 1 은 도보만. Phase 2 에서 'bike' 추가.


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


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    buildings_loaded: int
