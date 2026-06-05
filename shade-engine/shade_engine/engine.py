"""경로 그늘 판정 엔진.

경로 폴리라인을 일정 간격으로 샘플링하고, 각 샘플의 도착 예상 시각에 맞춰
태양 위치를 구한 뒤 건물 레이캐스팅으로 그늘/햇빛을 판정한다. 마지막에 경로의
그늘 비율(%)과 구간별 결과를 집계한다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from .buildings import Building
from .geo import LocalProjection, haversine_m
from .raycast import ProjectedBuilding, ShadeResult, is_point_shaded
from .sun import solar_position

DEFAULT_WALK_SPEED_MPS = 1.3  # 보행 평균 속도(약 4.7 km/h)
DEFAULT_SPACING_M = 10.0
_MAX_SHADOW_DISTANCE_CAP_M = 1500.0


@dataclass(frozen=True)
class SamplePoint:
    lat: float
    lon: float
    distance_m: float  # 출발점부터 누적 거리
    arrival: datetime
    sun_azimuth_deg: float
    sun_altitude_deg: float
    result: ShadeResult


@dataclass(frozen=True)
class RouteShade:
    samples: list[SamplePoint]
    total_distance_m: float
    shaded_count: int
    sunny_count: int

    @property
    def total_count(self) -> int:
        return len(self.samples)

    @property
    def shade_fraction(self) -> float:
        """그늘 비율 0~1 (태양이 떠 있는 샘플 기준; 전부 야간이면 1.0)."""
        considered = self.shaded_count + self.sunny_count
        if considered == 0:
            return 1.0
        return self.shaded_count / considered

    @property
    def shade_percent(self) -> float:
        return round(self.shade_fraction * 100.0, 1)

    @property
    def mean_confidence(self) -> float:
        if not self.samples:
            return 0.0
        return sum(s.result.confidence for s in self.samples) / len(self.samples)


def sample_polyline(
    coords: list[tuple[float, float]], spacing_m: float = DEFAULT_SPACING_M
) -> list[tuple[float, float, float]]:
    """폴리라인을 spacing_m 간격으로 샘플링.

    coords: [(lat, lon), ...]. 반환: [(lat, lon, cumulative_distance_m), ...]
    (시작점과 끝점은 항상 포함).
    """
    if not coords:
        return []
    if len(coords) == 1:
        return [(coords[0][0], coords[0][1], 0.0)]
    if spacing_m <= 0:
        raise ValueError("spacing_m must be > 0")

    out: list[tuple[float, float, float]] = [(coords[0][0], coords[0][1], 0.0)]
    cumulative = 0.0
    carry = 0.0  # 다음 샘플까지 남은 거리

    for (lat1, lon1), (lat2, lon2) in zip(coords, coords[1:]):
        seg_len = haversine_m(lat1, lon1, lat2, lon2)
        if seg_len < 1e-9:
            continue
        dist_into_seg = carry
        while dist_into_seg < seg_len:
            if dist_into_seg > 0:  # 세그먼트 시작점(=이전 끝점)은 중복이라 건너뜀
                frac = dist_into_seg / seg_len
                lat = lat1 + (lat2 - lat1) * frac
                lon = lon1 + (lon2 - lon1) * frac
                out.append((lat, lon, cumulative + dist_into_seg))
            dist_into_seg += spacing_m
        cumulative += seg_len
        carry = dist_into_seg - seg_len

    last = coords[-1]
    if out[-1][2] < cumulative - 1e-6:
        out.append((last[0], last[1], cumulative))
    return out


def _project_buildings(
    buildings: list[Building], proj: LocalProjection
) -> list[ProjectedBuilding]:
    projected: list[ProjectedBuilding] = []
    for b in buildings:
        ring_xy = tuple(proj.to_xy(lat, lon) for lat, lon in b.ring)
        if len(ring_xy) >= 3:
            projected.append(
                ProjectedBuilding(
                    ring_xy=ring_xy,
                    height_m=b.height_m,
                    height_estimated=b.height_estimated,
                    osm_id=b.osm_id,
                )
            )
    return projected


def compute_route_shade(
    coords: list[tuple[float, float]],
    depart: datetime,
    buildings: list[Building],
    *,
    spacing_m: float = DEFAULT_SPACING_M,
    walk_speed_mps: float = DEFAULT_WALK_SPEED_MPS,
    moving_sun: bool = True,
    min_altitude_deg: float = 0.5,
) -> RouteShade:
    """경로의 구간별 그늘/햇빛 판정 + 그늘 비율 집계.

    moving_sun=True 이면 보행 속도로 계산한 각 샘플 도착 시각의 태양 위치를 쓴다
    (긴 경로에서 이동 중 태양이 움직이는 효과 반영).
    """
    samples_geo = sample_polyline(coords, spacing_m)
    if not samples_geo:
        return RouteShade(samples=[], total_distance_m=0.0, shaded_count=0, sunny_count=0)

    lat0 = sum(p[0] for p in samples_geo) / len(samples_geo)
    lon0 = sum(p[1] for p in samples_geo) / len(samples_geo)
    proj = LocalProjection(lat0=lat0, lon0=lon0)
    projected = _project_buildings(buildings, proj)
    tallest = max((b.height_m for b in projected), default=0.0)

    out_samples: list[SamplePoint] = []
    shaded = sunny = 0

    for lat, lon, dist in samples_geo:
        arrival = depart + timedelta(seconds=dist / walk_speed_mps) if moving_sun else depart
        sun = solar_position(lat, lon, arrival)

        if sun.altitude_deg <= min_altitude_deg:
            result = is_point_shaded(
                proj.to_xy(lat, lon),
                sun.azimuth_deg,
                sun.altitude_deg,
                projected,
                min_altitude_deg=min_altitude_deg,
            )
        else:
            tan_alt = math.tan(math.radians(sun.altitude_deg))
            max_dist = (
                min(_MAX_SHADOW_DISTANCE_CAP_M, tallest / tan_alt) if tan_alt > 1e-6 else _MAX_SHADOW_DISTANCE_CAP_M
            )
            result = is_point_shaded(
                proj.to_xy(lat, lon),
                sun.azimuth_deg,
                sun.altitude_deg,
                projected,
                max_distance_m=max(max_dist, spacing_m),
                min_altitude_deg=min_altitude_deg,
            )

        if result.reason == "sunny":
            sunny += 1
        else:
            shaded += 1

        out_samples.append(
            SamplePoint(
                lat=lat,
                lon=lon,
                distance_m=dist,
                arrival=arrival,
                sun_azimuth_deg=sun.azimuth_deg,
                sun_altitude_deg=sun.altitude_deg,
                result=result,
            )
        )

    total_distance = samples_geo[-1][2]
    return RouteShade(
        samples=out_samples,
        total_distance_m=total_distance,
        shaded_count=shaded,
        sunny_count=sunny,
    )
