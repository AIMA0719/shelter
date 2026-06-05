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
    # 경로 탐색 제공자: 'straight'(오프라인) | 'kakao'
    directions_provider: str = os.getenv("SHELTER_DIRECTIONS_PROVIDER", "straight")
    kakao_rest_api_key: str | None = os.getenv("SHELTER_KAKAO_REST_API_KEY")
    # 건물 조회 시 경로 bbox 를 이 거리(m)만큼 확장(그림자 도달 범위 고려).
    bbox_margin_m: float = float(os.getenv("SHELTER_BBOX_MARGIN_M", "300"))
    cache_max_entries: int = int(os.getenv("SHELTER_CACHE_MAX_ENTRIES", "512"))


def get_settings() -> Settings:
    return Settings()
