"""FastAPI 앱 진입점.

엔드포인트:
  GET  /health      서비스 상태 + 적재된 건물 수
  POST /v1/shade    경로 그늘 판정(출발/도착 또는 명시 경로)
"""

from __future__ import annotations

import time

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .ratelimit import RateLimiter

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
    provider = get_provider(settings)
    cache = LRUCache(settings.cache_max_entries)

    # 저장소: DSN 이 있으면 PostGIS(서울 전역), 없으면 GeoJSON(MVP/권역).
    pois = None
    if settings.db_dsn:
        from .db.postgis_repo import PostGISBuildingsRepository, PostGISPoisRepository

        repo: object = PostGISBuildingsRepository(settings.db_dsn)
        pois = PostGISPoisRepository(settings.db_dsn)
    else:
        repo = GeoJSONBuildingsRepository(settings.buildings_geojson)
        # POI(GeoJSON)는 /v1/pois 에서만 필요 → 지연 로드(find_pois). 강제 로드 시
        # POI 파일 문제가 핵심 엔드포인트까지 죽이는 것을 피한다.

    # 보행 네트워크가 설정·존재하면 OSM 그래프 라우팅 사용(없으면 격자 폴백).
    walk_graph = None
    path = settings.walk_network_geojson
    if path and os.path.exists(path):
        from shade_engine.osm_graph import load_geojson_network

        walk_graph = load_geojson_network(path)

    return ShadeService(
        repo=repo, provider=provider, settings=settings, cache=cache, walk_graph=walk_graph, pois=pois
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

    _settings = settings or Settings()
    limiter = RateLimiter(_settings.rate_limit_per_min)
    trust_proxy = _settings.trust_proxy

    def _client_key(request) -> str:  # type: ignore[no-untyped-def]
        # 신뢰 프록시 뒤에서는 X-Forwarded-For 의 첫 IP(원 클라이언트)를 사용.
        if trust_proxy:
            xff = request.headers.get("x-forwarded-for")
            if xff:
                return xff.split(",")[0].strip()
        return request.client.host if request.client else "?"

    @app.middleware("http")
    async def _rate_limit(request, call_next):  # type: ignore[no-untyped-def]
        if not limiter.allow(_client_key(request), time.monotonic()):
            return JSONResponse(status_code=429, content={"detail": "요청이 너무 많습니다."})
        return await call_next(request)

    # GET + HEAD 둘 다 허용 — UptimeRobot 무료 플랜은 HEAD 로만 핑하기 때문(콜드 스타트 방지).
    @app.api_route("/health", methods=["GET", "HEAD"], response_model=HealthResponse)
    def health() -> HealthResponse:
        svc = get_service()
        # 아직 데이터 적재(또는 스키마 생성) 전이면 buildings 테이블이 없을 수 있다.
        # 그래도 헬스체크는 통과시켜야 한다(배포 직후 적재 전 단계에서 컨테이너가
        # 죽지 않도록). 카운트 실패는 0 으로 보고한다.
        try:
            loaded = svc.repo.count()
        except Exception:
            loaded = 0
        return HealthResponse(version=__version__, buildings_loaded=loaded)

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
