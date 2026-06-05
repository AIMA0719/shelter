"""레이캐스팅 그늘 판정 (엔진의 심장).

한 지점이 그늘인지 판정: 태양 방향(수평 방위각)으로 광선을 쏴, 그 경로상의
건물이 (태양 고도각으로 결정되는) 그림자 임계 높이보다 높으면 그늘이다.
지면 관측자(높이 0), 평지붕(flat roof) 가정의 1차 근사.

좌표는 로컬 ENU 미터 평면(x=동, y=북)에서 처리한다. 위경도 → xy 변환은 engine
계층에서 수행한다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

_EPS = 1e-9


@dataclass(frozen=True)
class ProjectedBuilding:
    """로컬 xy 평면으로 투영된 건물."""

    ring_xy: tuple[tuple[float, float], ...]
    height_m: float
    height_estimated: bool = False
    osm_id: str | None = None

    def bbox(self) -> tuple[float, float, float, float]:
        xs = [p[0] for p in self.ring_xy]
        ys = [p[1] for p in self.ring_xy]
        return (min(xs), min(ys), max(xs), max(ys))


@dataclass(frozen=True)
class ShadeResult:
    """한 지점의 그늘 판정 결과."""

    shaded: bool
    reason: str  # 'sunny' | 'building' | 'inside_building' | 'sun_below'
    confidence: float  # 0~1, 건물 높이 추정/경계 근접 시 하락
    blocker_id: str | None = None
    blocker_distance_m: float | None = None


def _point_in_ring(px: float, py: float, ring: tuple[tuple[float, float], ...]) -> bool:
    """다각형 내부 판정(ray casting). 경계 위는 내부로 간주하지 않는다(근사)."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > py) != (yj > py):
            x_cross = xi + (py - yi) / (yj - yi) * (xj - xi)
            if px < x_cross:
                inside = not inside
        j = i
    return inside


def _ray_segment_distance(
    ox: float, oy: float, dx: float, dy: float, ax: float, ay: float, bx: float, by: float
) -> float | None:
    """광선(원점 o, 단위방향 d)과 선분(a→b)의 교차 거리. 없으면 None."""
    v1x, v1y = ox - ax, oy - ay
    v2x, v2y = bx - ax, by - ay
    v3x, v3y = -dy, dx
    denom = v2x * v3x + v2y * v3y
    if abs(denom) < _EPS:
        return None  # 평행
    t1 = (v2x * v1y - v2y * v1x) / denom  # 광선 거리
    t2 = (v1x * v3x + v1y * v3y) / denom  # 선분 파라미터
    if t1 >= 0.0 and 0.0 <= t2 <= 1.0:
        return t1
    return None


def _ray_ring_min_distance(
    ox: float, oy: float, dx: float, dy: float, ring: tuple[tuple[float, float], ...]
) -> float | None:
    """광선과 폴리곤 외곽(모든 변)의 최단 교차 거리."""
    best: float | None = None
    n = len(ring)
    for i in range(n):
        ax, ay = ring[i]
        bx, by = ring[(i + 1) % n]
        d = _ray_segment_distance(ox, oy, dx, dy, ax, ay, bx, by)
        if d is not None and (best is None or d < best):
            best = d
    return best


def is_point_shaded(
    point_xy: tuple[float, float],
    sun_azimuth_deg: float,
    sun_altitude_deg: float,
    buildings: list[ProjectedBuilding],
    *,
    max_distance_m: float = 1000.0,
    min_altitude_deg: float = 0.5,
) -> ShadeResult:
    """한 지점이 그늘인지 판정한다.

    sun_altitude_deg 가 임계치 이하면 직사광선이 의미 없으므로 그늘로 본다.
    """
    if sun_altitude_deg <= min_altitude_deg:
        return ShadeResult(shaded=True, reason="sun_below", confidence=1.0)

    ox, oy = point_xy
    az = math.radians(sun_azimuth_deg)
    dx, dy = math.sin(az), math.cos(az)  # 태양을 향하는 수평 단위벡터(동,북)
    tan_alt = math.tan(math.radians(sun_altitude_deg))

    nearest_blocker_dist: float | None = None
    nearest_blocker_id: str | None = None
    confidence = 1.0

    for b in buildings:
        min_x, min_y, max_x, max_y = b.bbox()
        # bbox 가 광선 도달 범위 밖이면 스킵(빠른 거리 하한 프리필터)
        ddx = max(min_x - ox, 0.0, ox - max_x)
        ddy = max(min_y - oy, 0.0, oy - max_y)
        if math.hypot(ddx, ddy) > max_distance_m:
            continue

        if _point_in_ring(ox, oy, b.ring_xy):
            return ShadeResult(
                shaded=True,
                reason="inside_building",
                confidence=1.0 if not b.height_estimated else 0.7,
                blocker_id=b.osm_id,
                blocker_distance_m=0.0,
            )

        d = _ray_ring_min_distance(ox, oy, dx, dy, b.ring_xy)
        if d is None or d > max_distance_m:
            continue

        required = d * tan_alt  # 이 거리에서 태양을 가리려면 필요한 높이
        if b.height_m >= required:
            if nearest_blocker_dist is None or d < nearest_blocker_dist:
                nearest_blocker_dist = d
                nearest_blocker_id = b.osm_id
            # 경계(높이 ≈ 임계) 근접 + 추정 높이면 신뢰도 하락
            if required > 0 and b.height_estimated and b.height_m < required * 1.2:
                confidence = min(confidence, 0.6)

    if nearest_blocker_dist is not None:
        return ShadeResult(
            shaded=True,
            reason="building",
            confidence=confidence,
            blocker_id=nearest_blocker_id,
            blocker_distance_m=nearest_blocker_dist,
        )

    return ShadeResult(shaded=False, reason="sunny", confidence=confidence)
