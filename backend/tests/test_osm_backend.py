from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from shade_engine.demo import synthetic_scene
from shade_engine.osm_graph import load_geojson_network

from app.buildings_repo import InMemoryBuildingsRepository
from app.config import Settings
from app.directions import StraightLineProvider
from app.main import build_service, create_app, set_service
from app.models import LatLng, RoutesRequest
from app.shade_service import ShadeService

KST = timezone(timedelta(hours=9))
_WALK_NET = str(Path(__file__).resolve().parent.parent / "data" / "sample_walk_network.geojson")


def _osm_service() -> ShadeService:
    _, buildings = synthetic_scene()
    return ShadeService(
        repo=InMemoryBuildingsRepository(buildings),
        provider=StraightLineProvider(),
        settings=Settings(),
        walk_graph=load_geojson_network(_WALK_NET),
    )


def test_routes_use_osm_when_walk_graph_present():
    svc = _osm_service()
    resp = svc.plan_route_options(
        RoutesRequest(
            origin=LatLng(lat=37.49750, lon=127.0271),
            destination=LatLng(lat=37.49900, lon=127.0271),
            depart_time=datetime(2026, 7, 15, 16, 0, tzinfo=KST),
        )
    )
    assert resp.routing == "osm"
    assert {o.name for o in resp.options} == {"shortest", "balanced", "shadiest"}
    for o in resp.options:
        assert o.coords[0].lat == 37.49750 and o.coords[0].lon == 127.0271
        assert o.coords[-1].lat == 37.49900 and o.coords[-1].lon == 127.0271


def test_bike_mode_falls_back_to_grid_even_with_walk_graph():
    # 코덱스 회귀: 보행 전용 그래프를 자전거에 쓰면 안 됨 → 격자 폴백.
    svc = _osm_service()
    resp = svc.plan_route_options(
        RoutesRequest(
            origin=LatLng(lat=37.49750, lon=127.0271),
            destination=LatLng(lat=37.49900, lon=127.0271),
            depart_time=datetime(2026, 7, 15, 16, 0, tzinfo=KST),
            mode="bike",
        )
    )
    assert resp.routing == "grid"


def test_routes_fall_back_to_grid_when_outside_network():
    # 코덱스 회귀: 보행망 범위 밖 요청이면 OSM 대신 격자로 폴백.
    svc = _osm_service()
    resp = svc.plan_route_options(
        RoutesRequest(
            origin=LatLng(lat=37.6000, lon=127.2000),
            destination=LatLng(lat=37.6010, lon=127.2000),
            depart_time=datetime(2026, 7, 15, 16, 0, tzinfo=KST),
        )
    )
    assert resp.routing == "grid"


def test_routes_fall_back_to_grid_without_walk_graph():
    _, buildings = synthetic_scene()
    svc = ShadeService(
        repo=InMemoryBuildingsRepository(buildings),
        provider=StraightLineProvider(),
        settings=Settings(),
    )
    resp = svc.plan_route_options(
        RoutesRequest(
            origin=LatLng(lat=37.49750, lon=127.0270),
            destination=LatLng(lat=37.49900, lon=127.0270),
            depart_time=datetime(2026, 7, 15, 16, 0, tzinfo=KST),
        )
    )
    assert resp.routing == "grid"


def test_build_service_loads_walk_network_from_settings():
    set_service(None)
    svc = build_service(Settings(walk_network_geojson=_WALK_NET))
    assert svc.walk_graph is not None
    assert svc.walk_graph.node_count() > 0
    client = TestClient(create_app())  # set_service 미사용 → 기본 서비스, 핵심 동작 확인
    assert client.get("/health").status_code == 200
