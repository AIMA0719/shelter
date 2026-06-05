"""백엔드 설정 (환경변수 기반)."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_REPO_ROOT = _BACKEND_DIR.parent
_SHADE_ENGINE_DIR = _REPO_ROOT / "shade-engine"

# 모노레포 형제 패키지(shade_engine)를 import 경로에 추가.
if str(_SHADE_ENGINE_DIR) not in sys.path and _SHADE_ENGINE_DIR.exists():
    sys.path.insert(0, str(_SHADE_ENGINE_DIR))


@dataclass(frozen=True)
class Settings:
    # 건물 데이터: 로컬 GeoJSON(MVP). 추후 PostGIS 로 교체.
    buildings_geojson: str = os.getenv(
        "SHELTER_BUILDINGS_GEOJSON", str(_BACKEND_DIR / "data" / "sample_buildings.geojson")
    )
    pois_geojson: str = os.getenv(
        "SHELTER_POIS_GEOJSON", str(_BACKEND_DIR / "data" / "sample_pois.geojson")
    )
    # 보행 네트워크(LineString GeoJSON). 지정·존재하면 OSM 그래프 라우팅, 아니면 격자.
    walk_network_geojson: str = os.getenv("SHELTER_WALK_NETWORK_GEOJSON", "")
    # PostGIS DSN. 지정하면 건물/POI 를 GeoJSON 대신 PostGIS 에서 조회(서울 전역).
    db_dsn: str = os.getenv("SHELTER_DB_DSN", "")
    # 기상청(KMA) 서비스 키. 지정하면 stub 대신 실제 기상 데이터 사용.
    kma_service_key: str = os.getenv("SHELTER_KMA_SERVICE_KEY", "")
    # IP 당 분당 요청 한도(0 이면 비활성). 운영 폭주 방지.
    rate_limit_per_min: int = int(os.getenv("SHELTER_RATE_LIMIT_PER_MIN", "600"))
    # 경로 탐색 제공자: 'straight'(오프라인) | 'kakao'
    directions_provider: str = os.getenv("SHELTER_DIRECTIONS_PROVIDER", "straight")
    kakao_rest_api_key: str | None = os.getenv("SHELTER_KAKAO_REST_API_KEY")
    # 건물 조회 시 경로 bbox 를 이 거리(m)만큼 확장(그림자 도달 범위 고려).
    bbox_margin_m: float = float(os.getenv("SHELTER_BBOX_MARGIN_M", "300"))
    cache_max_entries: int = int(os.getenv("SHELTER_CACHE_MAX_ENTRIES", "512"))


def get_settings() -> Settings:
    return Settings()
