from datetime import datetime, timedelta, timezone

from shade_engine.demo import synthetic_scene
from shade_engine.suggest import best_departure, evaluate_departures

KST = timezone(timedelta(hours=9))


def _candidates():
    return [
        datetime(2026, 7, 15, 8, 0, tzinfo=KST),
        datetime(2026, 7, 15, 12, 0, tzinfo=KST),
        datetime(2026, 7, 15, 16, 0, tzinfo=KST),
    ]


def test_evaluate_preserves_order_and_length():
    route, buildings = synthetic_scene()
    evals = evaluate_departures(route, _candidates(), buildings)
    assert len(evals) == 3
    assert [e.depart for e in evals] == _candidates()


def test_best_departure_summer_prefers_shade():
    # 서편 고층 → 오후가 가장 그늘짐
    route, buildings = synthetic_scene()
    evals = evaluate_departures(route, _candidates(), buildings)
    best = best_departure(evals)
    assert best is not None
    assert best.depart.hour == 16


def test_best_departure_winter_prefers_sun():
    route, buildings = synthetic_scene()
    evals = evaluate_departures(route, _candidates(), buildings)
    best = best_departure(evals, prefer_sun=True)
    assert best is not None
    assert best.depart.hour in (8, 12)  # 그늘이 가장 적은 시각


def test_best_departure_empty():
    assert best_departure([]) is None
