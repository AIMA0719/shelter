"""가로수(수목) 그림자 캐스터 (Phase 2).

수목을 '수관 반경의 팔각형 발자국 + 수관 상단 높이'를 가진 장애물로 근사해 건물
레이캐스터를 그대로 재사용한다. 수관은 원형에 가깝지만 그림자 1차 근사에는 충분하다.
서울시 가로수 현황 오픈데이터(위치·수고·수관폭)를 이 모델로 적재한다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .buildings import Building

DEFAULT_TREE_HEIGHT_M = 7.0  # 가로수 평균 수고 가정
DEFAULT_CANOPY_RADIUS_M = 3.0  # 수관 반경 가정
_M_PER_DEG_LAT = 111_320.0


@dataclass(frozen=True)
class Tree:
    lat: float
    lon: float
    height_m: float = DEFAULT_TREE_HEIGHT_M
    canopy_radius_m: float = DEFAULT_CANOPY_RADIUS_M


def tree_to_building(tree: Tree, *, segments: int = 8) -> Building:
    """수목 → 팔각형 발자국·수관 높이 Building(장애물)으로 변환."""
    m_per_deg_lon = _M_PER_DEG_LAT * max(0.1, math.cos(math.radians(tree.lat)))
    ring: list[tuple[float, float]] = []
    for i in range(segments):
        theta = 2 * math.pi * i / segments
        dlat = (tree.canopy_radius_m * math.sin(theta)) / _M_PER_DEG_LAT
        dlon = (tree.canopy_radius_m * math.cos(theta)) / m_per_deg_lon
        ring.append((tree.lat + dlat, tree.lon + dlon))
    return Building(
        ring=tuple(ring),
        height_m=tree.height_m,
        height_estimated=True,  # 수목 높이는 항상 추정 → 신뢰도에 반영
        osm_id="tree",
    )


def trees_as_buildings(trees: list[Tree]) -> list[Building]:
    return [tree_to_building(t) for t in trees]
