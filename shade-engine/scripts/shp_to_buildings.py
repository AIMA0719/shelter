"""국토부 GIS건물통합정보(AL_D010, EPSG:5186) SHP → Shelter 건물 GeoJSON 변환.

서울 전역(약 70만 동)은 PostGIS 적재용으로 전체 변환하고, 인메모리 백엔드(MVP/권역)는
--bbox 로 권역만 잘라 쓴다. 좌표는 EPSG:5186(중부원점)→WGS84(EPSG:4326)로 재투영한다.

의존성: pyshp, pyproj (코어 엔진엔 불필요). 설치:
  pip install -e "shade-engine[gis]"   # 또는  pip install pyshp pyproj

속성 매핑(AL_D010):
  A16 = 건물 높이(m)        → height (있으면 우선, 실측값)
  A26 = 지상층수            → building:levels (높이 없을 때 층고 3m로 추정)
  A1  = 건물 고유번호       → id

예 (강남 권역만):
  python scripts/shp_to_buildings.py \
    --shp "C:/Users/Infocar/Downloads/_shelter_shp/AL_D010_11_20260509.shp" \
    --out ../backend/data/seoul_gangnam_buildings.geojson \
    --bbox 37.488 127.020 37.508 127.045

예 (서울 전역 → PostGIS 적재용 전체 변환, --bbox 생략):
  python scripts/shp_to_buildings.py --shp ...AL_D010_11_20260509.shp --out seoul_all_buildings.geojson
"""

from __future__ import annotations

import argparse
import json

SRC_EPSG = 5186  # Korea 2000 / Central Belt 2010
DEFAULT_LEVEL_HEIGHT_M = 3.0


def _height_props(rec) -> dict:
    """레코드 → height/building:levels 속성(추정 규칙 포함)."""
    props = {"building": "yes"}
    a1 = getattr(rec, "A1", None)
    if a1:
        props["id"] = str(a1)
    height = getattr(rec, "A16", None)  # 실측 높이(m)
    levels = getattr(rec, "A26", None)  # 지상층수
    if isinstance(height, (int, float)) and height > 0:
        props["height"] = str(round(float(height), 2))
    if isinstance(levels, (int, float)) and levels > 0:
        props["building:levels"] = str(int(levels))
    return props


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GIS건물통합정보 SHP → 건물 GeoJSON")
    parser.add_argument("--shp", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--bbox", nargs=4, type=float, default=None,
        metavar=("MIN_LAT", "MIN_LON", "MAX_LAT", "MAX_LON"),
        help="지정 시 해당 권역(위경도)만 변환",
    )
    parser.add_argument("--encoding", default="cp949")
    args = parser.parse_args(argv)

    import shapefile  # pyshp
    from pyproj import Transformer

    to_wgs = Transformer.from_crs(SRC_EPSG, 4326, always_xy=True)  # (x,y)->(lon,lat)
    to_src = Transformer.from_crs(4326, SRC_EPSG, always_xy=True)  # (lon,lat)->(x,y)

    # bbox 를 소스 좌표계로 변환(재투영 전에 값싸게 필터)
    src_bbox = None
    if args.bbox:
        min_lat, min_lon, max_lat, max_lon = args.bbox
        xs, ys = [], []
        for la, lo in [(min_lat, min_lon), (min_lat, max_lon), (max_lat, min_lon), (max_lat, max_lon)]:
            x, y = to_src.transform(lo, la)
            xs.append(x)
            ys.append(y)
        src_bbox = (min(xs), min(ys), max(xs), max(ys))

    reader = shapefile.Reader(args.shp, encoding=args.encoding)
    total = len(reader)
    written = 0
    scanned = 0
    h_real = h_est = 0

    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write('{"type":"FeatureCollection","features":[\n')
        first = True
        for sr in reader.iterShapeRecords():
            scanned += 1
            shp = sr.shape
            if not shp.points:
                continue
            if src_bbox is not None:
                bx0, by0, bx1, by1 = shp.bbox  # 소스 좌표계 bbox
                if bx1 < src_bbox[0] or bx0 > src_bbox[2] or by1 < src_bbox[1] or by0 > src_bbox[3]:
                    continue
            geo = shp.__geo_interface__  # 파트/홀 처리된 Polygon/MultiPolygon
            gtype = geo.get("type")
            rings_sets = []
            if gtype == "Polygon":
                rings_sets = [geo["coordinates"]]
            elif gtype == "MultiPolygon":
                rings_sets = list(geo["coordinates"])
            else:
                continue
            props = _height_props(sr.record)
            if "height" in props:
                h_real += 1
            else:
                h_est += 1
            for rings in rings_sets:
                if not rings:
                    continue
                exterior = rings[0]
                wgs = [list(to_wgs.transform(x, y)) for x, y in exterior]  # [lon,lat]
                if len(wgs) < 3:
                    continue
                feat = {"type": "Feature", "properties": props, "geometry": {"type": "Polygon", "coordinates": [wgs]}}
                fh.write(("" if first else ",\n") + json.dumps(feat, ensure_ascii=False))
                first = False
                written += 1
            if scanned % 100000 == 0:
                print(f"  스캔 {scanned}/{total} ... 기록 {written}")
        fh.write("\n]}\n")

    print(f"완료: {args.out}")
    print(f"  스캔 {scanned}동, 기록 {written}개 폴리곤 (실측높이 {h_real} / 층수추정 {h_est})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
