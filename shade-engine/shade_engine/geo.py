"""지리 좌표 ↔ 로컬 평면(미터) 변환 및 거리/방위 헬퍼.

도시 블록·경로 bbox처럼 좁은 영역에서는 등거리원통도법(equirectangular)
근사로 위경도를 로컬 ENU(동/북) 미터 평면에 충분히 정확히 매핑할 수 있다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# WGS84 기준 위도 1도당 거리(m). 경도는 cos(위도)로 보정한다.
_M_PER_DEG_LAT = 111_320.0
_M_PER_DEG_LON_EQUATOR = 111_320.0
EARTH_RADIUS_M = 6_371_000.0


@dataclass(frozen=True)
class LocalProjection:
    """기준점(lat0, lon0) 주변의 평평한 ENU 미터 평면.

    x = 동쪽(+), y = 북쪽(+). 좁은 영역에서만 사용할 것.
    """

    lat0: float
    lon0: float

    @property
    def _m_per_deg_lon(self) -> float:
        return _M_PER_DEG_LON_EQUATOR * math.cos(math.radians(self.lat0))

    def to_xy(self, lat: float, lon: float) -> tuple[float, float]:
        x = (lon - self.lon0) * self._m_per_deg_lon
        y = (lat - self.lat0) * _M_PER_DEG_LAT
        return (x, y)

    def to_latlon(self, x: float, y: float) -> tuple[float, float]:
        lon = self.lon0 + x / self._m_per_deg_lon
        lat = self.lat0 + y / _M_PER_DEG_LAT
        return (lat, lon)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 위경도 사이의 대권 거리(m)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """지점1→지점2 방위각(도, 북=0 시계방향). [0,360)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0
