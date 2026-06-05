-- Shelter PostGIS 스키마 (서울 전역 확장용)
-- 적용: psql "$SHELTER_DB_DSN" -f schema.sql  (PostGIS 확장 필요)

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS buildings (
    id               BIGSERIAL PRIMARY KEY,
    osm_id           TEXT,
    height_m         DOUBLE PRECISION NOT NULL,
    height_estimated BOOLEAN NOT NULL DEFAULT FALSE,
    geom             geometry(Polygon, 4326) NOT NULL
);
-- bbox 질의 가속(GiST 공간 인덱스)
CREATE INDEX IF NOT EXISTS buildings_geom_gist ON buildings USING GIST (geom);

CREATE TABLE IF NOT EXISTS pois (
    id    BIGSERIAL PRIMARY KEY,
    type  TEXT NOT NULL,
    name  TEXT,
    geom  geometry(Point, 4326) NOT NULL
);
CREATE INDEX IF NOT EXISTS pois_geom_gist ON pois USING GIST (geom);
