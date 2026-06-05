"""실제 OSM 보행 네트워크를 내려받아 GeoJSON 으로 저장하는 스크립트.

서울 한 권역(예: 강남)의 보행 도로를 받아 백엔드 라우팅에 쓸 캐시 파일을 만든다.

예:
    # 강남역 주변 약 1km x 1km
    python scripts/fetch_walk_network.py --bbox 37.495 127.025 37.503 127.034 \
        --out ../backend/data/gangnam_walk_network.geojson

저장 후 백엔드에서:
    set SHELTER_WALK_NETWORK_GEOJSON=...gangnam_walk_network.geojson  (Windows)
    export SHELTER_WALK_NETWORK_GEOJSON=...                            (bash)
그러면 /v1/routes 가 격자 대신 실제 OSM 보행 그래프로 그늘 라우팅을 수행한다.
"""

from __future__ import annotations

import argparse
import json

from shade_engine.osm_graph import fetch_walk_geojson, load_geojson_network


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OSM 보행망 다운로드 → GeoJSON")
    parser.add_argument(
        "--bbox",
        nargs=4,
        type=float,
        metavar=("MIN_LAT", "MIN_LON", "MAX_LAT", "MAX_LON"),
        required=True,
    )
    parser.add_argument("--out", required=True, help="저장할 GeoJSON 경로")
    args = parser.parse_args(argv)

    bbox = (args.bbox[0], args.bbox[1], args.bbox[2], args.bbox[3])
    print(f"Overpass 에서 보행망 다운로드: bbox={bbox}")
    fc = fetch_walk_geojson(bbox)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(fc, fh, ensure_ascii=False)

    graph = load_geojson_network(args.out)
    print(f"저장: {args.out}")
    print(f"보행 도로 {len(fc['features'])}개 → 노드 {graph.node_count()}, 엣지 {graph.edge_count()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
