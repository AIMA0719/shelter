"""출발 시간 추천 (Phase 3).

여러 후보 출발 시각에 대해 경로의 그늘 비율을 계산하고, 여름엔 가장 그늘진 시각,
겨울(prefer_sun)엔 가장 햇빛 많은 시각을 추천한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .buildings import Building
from .engine import compute_route_shade
from .trees import Tree


@dataclass(frozen=True)
class DepartureEvaluation:
    depart: datetime
    shade_fraction: float

    @property
    def shade_percent(self) -> float:
        return round(self.shade_fraction * 100.0, 1)


def evaluate_departures(
    coords: list[tuple[float, float]],
    candidates: list[datetime],
    buildings: list[Building],
    *,
    spacing_m: float = 10.0,
    walk_speed_mps: float = 1.3,
    trees: list[Tree] | None = None,
) -> list[DepartureEvaluation]:
    """후보 출발 시각별 그늘 비율을 계산한다(입력 순서 유지)."""
    out: list[DepartureEvaluation] = []
    for dt in candidates:
        rs = compute_route_shade(
            coords, dt, buildings, spacing_m=spacing_m, walk_speed_mps=walk_speed_mps, trees=trees
        )
        out.append(DepartureEvaluation(depart=dt, shade_fraction=rs.shade_fraction))
    return out


def best_departure(
    evaluations: list[DepartureEvaluation], *, prefer_sun: bool = False
) -> DepartureEvaluation | None:
    """추천 출발 시각. 기본은 가장 그늘진 시각, prefer_sun 이면 가장 햇빛 많은 시각."""
    if not evaluations:
        return None
    if prefer_sun:
        return min(evaluations, key=lambda e: e.shade_fraction)
    return max(evaluations, key=lambda e: e.shade_fraction)
