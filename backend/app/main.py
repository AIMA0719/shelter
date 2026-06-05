"""FastAPI 앱 진입점.

엔드포인트:
  GET  /health      서비스 상태 + 적재된 건물 수
  POST /v1/shade    경로 그늘 판정(출발/도착 또는 명시 경로)
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .buildings_repo import GeoJSONBuildingsRepository
from .cache import LRUCache
from .config import Settings
from .directions import get_provider
from .models import (
    DepartureSuggestRequest,
    DepartureSuggestResponse,
    HealthResponse,
    PoisResponse,
    RoutesRequest,
    RoutesResponse,
    ShadeRequest,
    ShadeResponse,
)
from .shade_service import ShadeService

import os

_service: ShadeService | None = None


def build_service(settings: Settings) -> ShadeService:
    repo = GeoJSONBuildingsRepository(settings.buildings_geojson)
    provider = get_provider(settings)
    cache = LRUCache(settings.cache_max_entries)
    # POI 데이터는 /v1/pois 에서만 필요하므로 지연 로드(find_pois)에 맡긴다.
    # 여기서 강제 로드하면 POI 파일 문제로 핵심 엔드포인트까지 죽는다.

    # 보행 네트워크가 설정·존재하면 OSM 그래프 라우팅 사용(없으면 격자 폴백).
    walk_graph = None
    path = settings.walk_network_geojson
    if path and os.path.exists(path):
        from shade_engine.osm_graph import load_geojson_network

        walk_graph = load_geojson_network(path)

    return ShadeService(
        repo=repo, provider=provider, settings=settings, cache=cache, walk_graph=walk_graph
    )


def get_service() -> ShadeService:
    """프로세스 싱글턴(GeoJSON 1회 적재). 테스트는 set_service 로 주입한다."""
    global _service
    if _service is None:
        _service = build_service(Settings())
    return _service


def set_service(service: ShadeService | None) -> None:
    global _service
    _service = service


def create_app(settings: Settings | None = None) -> FastAPI:
    # settings 가 주어지면 그 설정으로 서비스를 구성·주입한다(팩토리 인자 존중).
    # 미지정 시 기존에 주입된 서비스(테스트의 set_service)나 지연 기본 서비스를 쓴다.
    if settings is not None:
        set_service(build_service(settings))

    app = FastAPI(
        title="Shelter Shade API",
        version=__version__,
        summary="경로의 그늘/햇빛을 판정하는 API (Phase 1 MVP)",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # MVP. 운영에서는 앱 도메인으로 제한.
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        svc = get_service()
        return HealthResponse(version=__version__, buildings_loaded=svc.repo.count())

    @app.post("/v1/shade", response_model=ShadeResponse)
    def shade(req: ShadeRequest) -> ShadeResponse:
        svc = get_service()
        try:
            return svc.compute(req)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/v1/routes", response_model=RoutesResponse)
    def routes(req: RoutesRequest) -> RoutesResponse:
        svc = get_service()
        try:
            return svc.plan_route_options(req)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/v1/departure-suggest", response_model=DepartureSuggestResponse)
    def departure_suggest(req: DepartureSuggestRequest) -> DepartureSuggestResponse:
        svc = get_service()
        try:
            return svc.suggest_departures(req)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/v1/pois", response_model=PoisResponse)
    def pois(
        min_lat: float = Query(...),
        min_lon: float = Query(...),
        max_lat: float = Query(...),
        max_lon: float = Query(...),
    ) -> PoisResponse:
        svc = get_service()
        if min_lat > max_lat or min_lon > max_lon:
            raise HTTPException(status_code=422, detail="bbox 의 min 이 max 보다 큽니다.")
        return PoisResponse(pois=svc.find_pois(min_lat, min_lon, max_lat, max_lon))

    app.state.get_service = get_service  # 테스트에서 접근/오버라이드용
    return app


app = create_app()
