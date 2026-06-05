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
    args = parser.parse_args(argv)

    try:
        import psycopg
    except ImportError:
        print("psycopg 필요: pip install 'psycopg[binary]'", file=sys.stderr)
        return 2

    with psycopg.connect(args.dsn) as conn, conn.cursor() as cur:
        if args.buildings:
            buildings = load_geojson(args.buildings)
            for b in buildings:
                cur.execute(
                    "INSERT INTO buildings (osm_id, height_m, height_estimated, geom) "
                    "VALUES (%s, %s, %s, ST_GeomFromText(%s, 4326))",
                    (b.osm_id, b.height_m, b.height_estimated, building_to_wkt(b)),
                )
            print(f"건물 {len(buildings)}동 적재")
        if args.pois:
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
