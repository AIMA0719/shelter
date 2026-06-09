"""GeoJSON(건물/POI) → PostGIS 적재 스크립트.

예:
    python -m app.db.ingest --dsn "postgresql://shelter:shelter@localhost:5432/shelter" \
        --buildings data/gangnam_buildings.geojson --pois data/sample_pois.geojson

스키마는 app/db/schema.sql 로 먼저 적용한다.
"""

from __future__ import annotations

import argparse
import json
import sys

from shade_engine.buildings import Building, load_geojson


def building_to_wkt(b: Building) -> str:
    """Building(ring [(lat,lon)]) → WKT POLYGON((lon lat, ...))(닫힌 링)."""
    pts = list(b.ring)
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    coords = ", ".join(f"{lon} {lat}" for lat, lon in pts)
    return f"POLYGON(({coords}))"


def _load_pois(path: str) -> list[tuple[str, str | None, float, float]]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    rows = []
    for feat in data.get("features", []):
        geom = feat.get("geometry") or {}
        if geom.get("type") != "Point":
            continue
        c = geom.get("coordinates") or []
        if len(c) < 2:
            continue
        props = feat.get("properties") or {}
        rows.append((str(props.get("type", "shade_shelter")), props.get("name"), float(c[1]), float(c[0])))
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GeoJSON → PostGIS 적재")
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--buildings")
    parser.add_argument("--pois")
    parser.add_argument(
        "--replace", action="store_true",
        help="적재 전 기존 행을 비움(TRUNCATE) — 전역 재적재 시 중복 방지",
    )
    parser.add_argument(
        "--init-schema", metavar="SCHEMA_SQL",
        help="적재 전 이 schema.sql 을 실행(PostGIS 확장+테이블 생성). 새 DB(예: Render 90일 재생성) 첫 적재 시 사용",
    )
    args = parser.parse_args(argv)

    try:
        import psycopg
    except ImportError:
        print("psycopg 필요: pip install 'psycopg[binary]'", file=sys.stderr)
        return 2

    with psycopg.connect(args.dsn) as conn, conn.cursor() as cur:
        if args.init_schema:
            with open(args.init_schema, encoding="utf-8") as fh:
                cur.execute(fh.read())
            print(f"스키마 적용: {args.init_schema}")
        if args.buildings:
            if args.replace:
                cur.execute("TRUNCATE buildings RESTART IDENTITY")
            buildings = load_geojson(args.buildings)
            # 서울 전역(약 70만 동)은 한 줄씩 INSERT 하면 너무 느리다. PostGIS geometry 가
            # EWKT 텍스트 입력을 받는 점을 이용해 단일 COPY 스트림으로 적재한다.
            written = 0
            with cur.copy(
                "COPY buildings (osm_id, height_m, height_estimated, geom) FROM STDIN"
            ) as copy:
                for b in buildings:
                    copy.write_row(
                        (b.osm_id, b.height_m, b.height_estimated, f"SRID=4326;{building_to_wkt(b)}")
                    )
                    written += 1
                    if written % 100000 == 0:
                        print(f"  건물 적재 {written}/{len(buildings)} ...")
            print(f"건물 {len(buildings)}동 적재")
        if args.pois:
            if args.replace:
                cur.execute("TRUNCATE pois RESTART IDENTITY")
            rows = _load_pois(args.pois)
            for ptype, name, lat, lon in rows:
                cur.execute(
                    "INSERT INTO pois (type, name, geom) "
                    "VALUES (%s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))",
                    (ptype, name, lon, lat),
                )
            print(f"POI {len(rows)}개 적재")
        conn.commit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
