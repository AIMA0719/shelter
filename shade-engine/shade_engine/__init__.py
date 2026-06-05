"""Shelter 그늘 엔진 (Phase 0 타당성 프로토타입).

태양 위치 + 건물 높이로 경로의 각 지점이 그늘인지 햇빛인지 판정한다.
순수 파이썬/표준 라이브러리만으로 동작하는 코어(geo/sun/raycast/engine)와,
선택적 확장(overpass OSM 추출, viz 시각화)으로 구성된다.
"""

from .geo import LocalProjection, bearing_deg, haversine_m
from .sun import SolarPosition, solar_position
from .buildings import Building, estimate_height_m, load_geojson
from .raycast import ShadeResult, is_point_shaded
from .engine import RouteShade, SamplePoint, compute_route_shade, sample_polyline
from .routing import RouteOption, plan_routes
from .trees import Tree, tree_to_building, trees_as_buildings
from .comfort import comfort_score
from .suggest import DepartureEvaluation, best_departure, evaluate_departures

__all__ = [
    "LocalProjection",
    "bearing_deg",
    "haversine_m",
    "SolarPosition",
    "solar_position",
    "Building",
    "estimate_height_m",
    "load_geojson",
    "ShadeResult",
    "is_point_shaded",
    "RouteShade",
    "SamplePoint",
    "compute_route_shade",
    "sample_polyline",
    "RouteOption",
    "plan_routes",
    "Tree",
    "tree_to_building",
    "trees_as_buildings",
    "comfort_score",
    "DepartureEvaluation",
    "best_departure",
    "evaluate_departures",
]

__version__ = "0.1.0"
