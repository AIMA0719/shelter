from datetime import datetime, timedelta, timezone

from shade_engine.engine import compute_route_shade
from shade_engine.trees import Tree, tree_to_building, trees_as_buildings

KST = timezone(timedelta(hours=9))


def test_tree_to_building_shape_and_height():
    t = Tree(lat=37.5, lon=127.0, height_m=8.0, canopy_radius_m=3.0)
    b = tree_to_building(t)
    assert len(b.ring) == 8  # 팔각형
    assert b.height_m == 8.0
    assert b.height_estimated is True


def test_trees_add_shade_to_route():
    # 건물 없이, 경로 서쪽에 가로수 → 오후(서쪽 태양)에 그늘 발생
    route = [(37.50000, 127.0000), (37.50005, 127.0000)]
    # 경로 약 5m 서쪽의 가로수
    tree = Tree(lat=37.50002, lon=127.0000 - 0.0000566, height_m=8.0, canopy_radius_m=3.0)

    depart = datetime(2026, 7, 15, 16, 0, tzinfo=KST)
    without = compute_route_shade(route, depart, [], spacing_m=5.0)
    with_trees = compute_route_shade(route, depart, [], spacing_m=5.0, trees=[tree])

    assert without.shade_fraction == 0.0
    assert with_trees.shade_fraction > without.shade_fraction


def test_trees_as_buildings_count():
    trees = [Tree(lat=37.5, lon=127.0), Tree(lat=37.501, lon=127.001)]
    assert len(trees_as_buildings(trees)) == 2
