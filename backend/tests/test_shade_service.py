from datetime import datetime, timedelta, timezone

from shade_engine.demo import synthetic_scene

from app.buildings_repo import InMemoryBuildingsRepository
from app.config import Settings
from app.directions import StraightLineProvider
from app.models import LatLng, ShadeRequest
from app.shade_service import ShadeService

KST = timezone(timedelta(hours=9))


def _service():
    _, buildings = synthetic_scene()
    repo = InMemoryBuildingsRepository(buildings)
    return ShadeService(repo=repo, provider=StraightLineProvider(), settings=Settings())


def _coords():
    route, _ = synthetic_scene()
    return [LatLng(lat=lat, lon=lon) for lat, lon in route]


def test_afternoon_more_shade_than_morning():
    svc = _service()
    morning = svc.compute(
        ShadeRequest(coords=_coords(), depart_time=datetime(2026, 7, 15, 8, 0, tzinfo=KST))
    )
    afternoon = svc.compute(
        ShadeRequest(coords=_coords(), depart_time=datetime(2026, 7, 15, 16, 0, tzinfo=KST))
    )
    assert afternoon.shade_percent > morning.shade_percent
    assert afternoon.shade_percent > 50.0
    assert afternoon.building_count >= 3
    assert len(afternoon.segments) == afternoon.sample_count - 1


def test_cache_hit_on_repeat():
    svc = _service()
    req = ShadeRequest(coords=_coords(), depart_time=datetime(2026, 7, 15, 16, 0, tzinfo=KST))
    first = svc.compute(req)
    second = svc.compute(req)
    assert first.cached is False
    assert second.cached is True
    assert first.shade_percent == second.shade_percent


def test_origin_destination_uses_provider():
    svc = _service()
    req = ShadeRequest(
        origin=LatLng(lat=37.49750, lon=127.0270),
        destination=LatLng(lat=37.49900, lon=127.0270),
        depart_time=datetime(2026, 7, 15, 16, 0, tzinfo=KST),
    )
    resp = svc.compute(req)
    assert resp.provider == "straight"
    assert resp.sample_count > 0
    assert 0.0 <= resp.shade_percent <= 100.0


def test_segments_have_valid_confidence():
    svc = _service()
    resp = svc.compute(
        ShadeRequest(coords=_coords(), depart_time=datetime(2026, 7, 15, 16, 0, tzinfo=KST))
    )
    for seg in resp.segments:
        assert 0.0 <= seg.confidence <= 1.0
        assert seg.reason in {"sunny", "building", "inside_building", "sun_below"}
