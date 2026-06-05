"""한 권역의 OSM 건물 + 보행 네트워크를 한 번에 받아 백엔드 데이터로 저장.

키·유료 데이터 없이 OSM 만으로 실제 권역을 부팅한다(MVP/권역 단위로 충분).

예 (강남역 주변 약 1.2km x 1.2km):
    python scripts/fetch_district.py --name gangnam \
        --bbox 37.495 127.025 37.503 127.034

생성:
    backend/data/gangnam_buildings.geojson
    backend/data/gangnam_walk_network.geojson
이후 백엔드 실행 전 환경변수만 지정하면 실제 데이터로 동작한다(스크립트가 안내).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from shade_engine.buildings import load_geojson
from shade_engine.osm_graph import fetch_walk_geojson, load_geojson_network
from shade_engine.overpass import fetch_buildings_geojson

_BACKEND_DATA = Path(__file__).resolve().parent.parent.parent / "backend" / "data"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="권역 OSM 건물+보행망 다운로드")
    parser.add_argument("--name", required=True, help="권역 이름(파일 접두사)")
    parser.add_argument(
        "--bbox", nargs=4, type=float, required=True,
        metavar=("MIN_LAT", "MIN_LON", "MAX_LAT", "MAX_LON"),
    )
    parser.add_argument("--out-dir", default=str(_BACKEND_DATA), help="저장 디렉터리")
    args = parser.parse_args(argv)

    bbox = (args.bbox[0], args.bbox[1], args.bbox[2], args.bbox[3])
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    b_path = out_dir / f"{args.name}_buildings.geojson"
    w_path = out_dir / f"{args.name}_walk_network.geojson"

    print(f"[1/2] 건물 다운로드 bbox={bbox} ...")
    with open(b_path, "w", encoding="utf-8") as fh:
        json.dump(fetch_buildings_geojson(bbox), fh, ensure_ascii=False)
    nb = len(load_geojson(str(b_path)))
    print(f"      저장: {b_path} (건물 {nb}동)")

    print(f"[2/2] 보행망 다운로드 ...")
    with open(w_path, "w", encoding="utf-8") as fh:
        json.dump(fetch_walk_geojson(bbox), fh, ensure_ascii=False)
    g = load_geojson_network(str(w_path))
    print(f"      저장: {w_path} (노드 {g.node_count()}, 엣지 {g.edge_count()})")

    print("\n백엔드 실행 전 환경변수 지정:")
    print(f"  (bash)       export SHELTER_BUILDINGS_GEOJSON={b_path}")
    print(f"               export SHELTER_WALK_NETWORK_GEOJSON={w_path}")
    print(f"  (PowerShell) $env:SHELTER_BUILDINGS_GEOJSON='{b_path}'")
    print(f"               $env:SHELTER_WALK_NETWORK_GEOJSON='{w_path}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
