"""가로수(수목) 저장소 (Phase 2 — 백엔드 연동).

가로수 현황 Point GeoJSON(위치 + 선택적 수고/수관폭)을 적재해 bbox 로 조회하고
shade_engine.Tree 로 변환한다. shade_service 가 경로 주변 가로수를
compute_route_shade(trees=...) 에 넘겨 '건물/가로수 레이캐스팅'(README) 의 가로수
그림자를 실제 응답에 반영한다. 건물 저장소와 동일하게 그리드 공간 인덱스를 쓴다.

GeoJSON properties 예: {"height_m": 8, "canopy_radius_m": 3.5}. 없으면 기본값
(shade_engine.trees 의 평균 수고/수관 반경)을 사용한다.
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Protocol

from shade_engine.trees import (
    DEFAULT_CANOPY_RADIUS_M,
    DEFAULT_TREE_HEIGHT_M,
    Tree,
)

_CELL_DEG = 0.003  # 약 330m 격자(건물 저장소와 동일)


class TreesRepository(Protocol):
    def query_bbox(
        self, min_lat: float, min_lon: float, max_lat: float, max_lon: float
    ) -> list[Tree]:
        ...

    def count(self) -> int:
        ...


class _IndexedTrees:
    """그리드 공간 인덱스 기반 bbox 질의 공통 구현(수목은 점이라 셀 1개에 귀속)."""

    def _build_index(self, trees: list[Tree]) -> None:
        self._trees = trees
        self._grid: dict[tuple[int, int], list[Tree]] = defaultdict(list)
        for t in trees:
            self._grid[(int(t.lat // _CELL_DEG), int(t.lon // _CELL_DEG))].append(t)

    def query_bbox(
        self, min_lat: float, min_lon: float, max_lat: float, max_lon: float
    ) -> list[Tree]:
        out: list[Tree] = []
        for cx in range(int(min_lat // _CELL_DEG), int(max_lat // _CELL_DEG) + 1):
            for cy in range(int(min_lon // _CELL_DEG), int(max_lon // _CELL_DEG) + 1):
                for t in self._grid.get((cx, cy), ()):
                    if min_lat <= t.lat <= max_lat and min_lon <= t.lon <= max_lon:
                        out.append(t)
        return out

    def count(self) -> int:
        return len(self._trees)


class GeoJSONTreesRepository(_IndexedTrees):
    """가로수 Point GeoJSON 을 1회 적재 후 그리드 인덱스로 질의."""

    def __init__(self, path: str) -> None:
        self._build_index(_load(path))


class InMemoryTreesRepository(_IndexedTrees):
    """테스트/주입용: Tree 리스트를 직접 인덱싱."""

    def __init__(self, trees: list[Tree]) -> None:
        self._build_index(list(trees))


def _coerce_float(value: object, default: float) -> float:
    try:
        f = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return f if f > 0 else default


def _load(path: str) -> list[Tree]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    trees: list[Tree] = []
    for feat in data.get("features", []):
        geom = feat.get("geometry") or {}
        if geom.get("type") != "Point":
            continue
        coords = geom.get("coordinates") or []
        if len(coords) < 2:
            continue
        props = feat.get("properties") or {}
        trees.append(
            Tree(
                lat=float(coords[1]),
                lon=float(coords[0]),
                height_m=_coerce_float(props.get("height_m"), DEFAULT_TREE_HEIGHT_M),
                canopy_radius_m=_coerce_float(
                    props.get("canopy_radius_m"), DEFAULT_CANOPY_RADIUS_M
                ),
            )
        )
    return trees
