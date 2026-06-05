"""FastAPI 앱 진입점.

엔드포인트:
  GET  /health      서비스 상태 + 적재된 건물 수
  POST /v1/shade    경로 그늘 판정(출발/도착 또는 명시 경로)
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .buildings_repo import GeoJSONBuildingsRepository
from .cache import LRUCache
from .config import Settings
from .directions import get_provider
from .models import HealthResponse, ShadeRequest, ShadeResponse
from .shade_service import ShadeService

_service: ShadeService | None = None


def build_service(settings: Settings) -> ShadeService:
    repo = GeoJSONBuildingsRepository(settings.buildings_geojson)
    provider = get_provider(settings)
    cache = LRUCache(settings.cache_max_entries)
    return ShadeService(repo=repo, provider=provider, settings=settings, cache=cache)


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

    app.state.get_service = get_service  # 테스트에서 접근/오버라이드용
    return app


app = create_app()
