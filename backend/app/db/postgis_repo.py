"""PostGIS 저장소 — 건물/POI 를 공간 인덱스(GiST)로 bbox 질의.

GeoJSON 저장소와 동일한 인터페이스(query_bbox/count)라 main.build_service 에서
교체만 하면 된다. psycopg(v3) 가 필요하며, 없으면 인스턴스 생성 시 안내한다.
순수 매핑 함수(_polygon_geojson_to_ring/_row_to_building)는 DB 없이 테스트한다.
"""

from __future__ import annotations

import json

from shade_engine.buildings import Building

from ..models import Poi


def _polygon_geojson_to_ring(geojson_str: str) -> tuple[tuple[float, float], ...]:
    """ST_AsGeoJSON(Polygon) 문자열 → 외곽 링 [(lat, lon), ...]."""
    geom = json.loads(geojson_str)
    coords = geom.get("coordinates") or []
    if geom.get("type") == "MultiPolygon":
        exterior = coords[0][0] if coords and coords[0] else []
    else:  # Polygon
        exterior = coords[0] if coords else []
    return tuple((float(pt[1]), float(pt[0])) for pt in exterior if len(pt) >= 2)


def _row_to_building(
    height_m: float, height_estimated: bool, geojson_str: str, osm_id: str | None
) -> Building | None:
    ring = _polygon_geojson_to_ring(geojson_str)
    if len(ring) < 3:
        return None
    return Building(
        ring=ring, height_m=float(height_m), height_estimated=bool(height_estimated), osm_id=osm_id
    )


def _require_psycopg():
    try:
        import psycopg  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - 환경 의존
        raise RuntimeError(
            "PostGIS 저장소에는 psycopg 가 필요합니다: pip install 'psycopg[binary]'"
        ) from exc
    return psycopg


class PostGISBuildingsRepository:
    def __init__(self, dsn: str) -> None:
        self._psycopg = _require_psycopg()
        self._dsn = dsn

    def query_bbox(
        self, min_lat: float, min_lon: float, max_lat: float, max_lon: float
    ) -> list[Building]:
        sql = (
            "SELECT height_m, height_estimated, ST_AsGeoJSON(geom), osm_id "
            "FROM buildings "
            "WHERE geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)"
        )
        out: list[Building] = []
        with self._psycopg.connect(self._dsn) as conn, conn.cursor() as cur:
            cur.execute(sql, (min_lon, min_lat, max_lon, max_lat))
            for height_m, estimated, geojson_str, osm_id in cur.fetchall():
                b = _row_to_building(height_m, estimated, geojson_str, osm_id)
                if b is not None:
                    out.append(b)
        return out

    def query_corridor(
        self, coords: list[tuple[float, float]], radius_m: float
    ) -> list[Building]:
        """경로(coords=[(lat,lon)]) 주변 radius_m 이내 건물만 조회.

        긴 대각선 경로에서 bbox 사각형은 실제 경로보다 훨씬 넓어 건물을 과도하게
        가져온다(직렬화/적재 비용↑). 경로 라인 버퍼(코리도)로 좁힌다.
        `geom && ST_Expand(line)` 로 GiST 인덱스 프리필터 후 ST_DWithin(geography)
        으로 정확히 거른다 — 반환 행이 줄어 ST_AsGeoJSON 직렬화 비용이 크게 준다.
        """
        if not coords:
            return []
        if len(coords) == 1:
            lat, lon = coords[0]
            line_wkt = f"POINT({lon} {lat})"
        else:
            pts = ", ".join(f"{lon} {lat}" for lat, lon in coords)
            line_wkt = f"LINESTRING({pts})"
        # 평면(geometry) ST_DWithin — GiST 인덱스를 직접 쓰고 거리계산이 가볍다.
        # 반경은 도(degree) 단위(rdeg). 위도 37.5°N 에서 경도 1도가 더 짧아 동서로 약간
        # 넓게 잡히지만 코리도로는 넉넉해 무방하다. geography 캐스트(무거움)는 피한다.
        sql = (
            "SELECT height_m, height_estimated, ST_AsGeoJSON(geom), osm_id FROM buildings "
            "WHERE ST_DWithin(geom, ST_GeomFromText(%(wkt)s, 4326), %(rdeg)s)"
        )
        params = {
            "wkt": line_wkt,
            "rdeg": radius_m / 111_320.0,
        }
        out: list[Building] = []
        with self._psycopg.connect(self._dsn) as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            for height_m, estimated, geojson_str, osm_id in cur.fetchall():
                b = _row_to_building(height_m, estimated, geojson_str, osm_id)
                if b is not None:
                    out.append(b)
        return out

    def count(self) -> int:
        with self._psycopg.connect(self._dsn) as conn, conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM buildings")
            return int(cur.fetchone()[0])


class PostGISPoisRepository:
    def __init__(self, dsn: str) -> None:
        self._psycopg = _require_psycopg()
        self._dsn = dsn

    def query_bbox(
        self, min_lat: float, min_lon: float, max_lat: float, max_lon: float
    ) -> list[Poi]:
        sql = (
            "SELECT type, name, ST_Y(geom), ST_X(geom) FROM pois "
            "WHERE geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)"
        )
        out: list[Poi] = []
        with self._psycopg.connect(self._dsn) as conn, conn.cursor() as cur:
            cur.execute(sql, (min_lon, min_lat, max_lon, max_lat))
            for ptype, name, lat, lon in cur.fetchall():
                out.append(Poi(lat=float(lat), lon=float(lon), type=str(ptype), name=name))
        return out

    def count(self) -> int:
        with self._psycopg.connect(self._dsn) as conn, conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM pois")
            return int(cur.fetchone()[0])
