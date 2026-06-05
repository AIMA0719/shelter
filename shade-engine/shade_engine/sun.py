"""태양 위치 계산 (NOAA Solar Position Algorithm).

위경도 + 시각(UTC)으로 태양의 방위각(azimuth)과 고도각(altitude)을 구한다.
외부 의존성 없이 표준 라이브러리만 사용하며, 정확도는 그늘 판정 용도로 충분하다
(고도/방위 오차 ~0.01도 수준). NOAA Solar Calculator 공식을 따른다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class SolarPosition:
    """태양 위치. 방위각은 북=0 시계방향(도), 고도각은 지평선=0 위쪽(도)."""

    azimuth_deg: float
    altitude_deg: float
    declination_deg: float
    is_up: bool  # 태양이 지평선 위에 있는지(고도 > 0)


def _julian_day(dt_utc: datetime) -> float:
    """UTC datetime → 율리우스일(Julian Date)."""
    year, month = dt_utc.year, dt_utc.month
    a = (14 - month) // 12
    y = year + 4800 - a
    m = month + 12 * a - 3
    jdn = (
        dt_utc.day
        + (153 * m + 2) // 5
        + 365 * y
        + y // 4
        - y // 100
        + y // 400
        - 32045
    )
    day_fraction = (
        (dt_utc.hour - 12) / 24.0
        + dt_utc.minute / 1440.0
        + (dt_utc.second + dt_utc.microsecond / 1e6) / 86400.0
    )
    return jdn + day_fraction


def _refraction_correction_deg(elevation_deg: float) -> float:
    """대기 굴절 보정(도). 지평선 근처에서 태양이 실제보다 높아 보이는 효과."""
    if elevation_deg > 85.0:
        return 0.0
    te = math.tan(math.radians(elevation_deg))
    if elevation_deg > 5.0:
        r = 58.1 / te - 0.07 / te**3 + 0.000086 / te**5
    elif elevation_deg > -0.575:
        r = 1735.0 + elevation_deg * (
            -518.2 + elevation_deg * (103.4 + elevation_deg * (-12.79 + elevation_deg * 0.711))
        )
    else:
        r = -20.774 / te
    return r / 3600.0


def solar_position(
    lat: float, lon: float, dt: datetime, *, apply_refraction: bool = True
) -> SolarPosition:
    """위경도 + 시각의 태양 위치.

    dt 가 tz-naive 이면 UTC 로 간주한다. lon 은 동경(+).
    """
    dt_utc = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)

    jd = _julian_day(dt_utc)
    t = (jd - 2451545.0) / 36525.0  # 율리우스 세기 (J2000 기준)

    # 태양 기하 평균 황경 / 평균 근점이각
    l0 = (280.46646 + t * (36000.76983 + 0.0003032 * t)) % 360.0
    m = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)

    m_rad = math.radians(m)
    sin_m, sin_2m, sin_3m = math.sin(m_rad), math.sin(2 * m_rad), math.sin(3 * m_rad)
    c = (
        sin_m * (1.914602 - t * (0.004817 + 0.000014 * t))
        + sin_2m * (0.019993 - 0.000101 * t)
        + sin_3m * 0.000289
    )

    true_long = l0 + c
    omega = 125.04 - 1934.136 * t
    app_long = true_long - 0.00569 - 0.00478 * math.sin(math.radians(omega))

    eps0 = 23.0 + (26.0 + (21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))) / 60.0) / 60.0
    eps = eps0 + 0.00256 * math.cos(math.radians(omega))

    eps_rad = math.radians(eps)
    app_long_rad = math.radians(app_long)
    declination = math.degrees(math.asin(math.sin(eps_rad) * math.sin(app_long_rad)))

    # 균시차(Equation of Time, 분)
    var_y = math.tan(eps_rad / 2.0) ** 2
    l0_rad = math.radians(l0)
    eot = 4.0 * math.degrees(
        var_y * math.sin(2 * l0_rad)
        - 2 * e * sin_m
        + 4 * e * var_y * sin_m * math.cos(2 * l0_rad)
        - 0.5 * var_y * var_y * math.sin(4 * l0_rad)
        - 1.25 * e * e * math.sin(2 * m_rad)
    )

    # 진태양시 / 시간각 (UTC 기준이므로 timezone 항=0)
    utc_minutes = dt_utc.hour * 60 + dt_utc.minute + dt_utc.second / 60.0
    true_solar_time = (utc_minutes + eot + 4.0 * lon) % 1440.0
    hour_angle = true_solar_time / 4.0 - 180.0
    if hour_angle < -180.0:
        hour_angle += 360.0

    lat_rad = math.radians(lat)
    decl_rad = math.radians(declination)
    ha_rad = math.radians(hour_angle)

    cos_zenith = math.sin(lat_rad) * math.sin(decl_rad) + math.cos(lat_rad) * math.cos(
        decl_rad
    ) * math.cos(ha_rad)
    cos_zenith = max(-1.0, min(1.0, cos_zenith))
    zenith = math.degrees(math.acos(cos_zenith))
    elevation = 90.0 - zenith

    # 방위각 (북=0 시계방향)
    sin_zenith = math.sin(math.radians(zenith))
    if abs(sin_zenith) < 1e-9:
        azimuth = 0.0  # 천정/천저 특이점
    else:
        cos_az = (math.sin(lat_rad) * cos_zenith - math.sin(decl_rad)) / (
            math.cos(lat_rad) * sin_zenith
        )
        cos_az = max(-1.0, min(1.0, cos_az))
        az_core = math.degrees(math.acos(cos_az))
        azimuth = (az_core + 180.0) % 360.0 if hour_angle > 0 else (540.0 - az_core) % 360.0

    if apply_refraction:
        elevation += _refraction_correction_deg(elevation)

    return SolarPosition(
        azimuth_deg=azimuth,
        altitude_deg=elevation,
        declination_deg=declination,
        is_up=elevation > 0.0,
    )
