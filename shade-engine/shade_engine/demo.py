"""Phase 0 데모: 합성 데이터로 그늘 엔진을 오프라인 시연.

강남풍 남북 도로 + 서편의 고층 건물을 만들고, 아침/오후 두 시각에 대해 경로의
그늘 비율이 어떻게 달라지는지 보여준다. 네트워크 없이 동작한다.

    python -m shade_engine.demo            # 요약 출력
    python -m shade_engine.demo --html out.html  # 오후 케이스 지도 저장
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

from .buildings import Building
from .engine import compute_route_shade

KST = timezone(timedelta(hours=9))

# 강남역 부근. 경도 0.0001도 ≈ 8.8m (위도 37.5)
_ROUTE_LON = 127.0270
_ROUTE = [(37.49750 + i * 0.00015, _ROUTE_LON) for i in range(11)]  # 남→북 약 165m


def _rect(min_lat: float, max_lat: float, min_lon: float, max_lon: float, height: float) -> Building:
    ring = (
        (min_lat, min_lon),
        (min_lat, max_lon),
        (max_lat, max_lon),
        (max_lat, min_lon),
    )
    return Building(ring=ring, height_m=height, height_estimated=False)


def synthetic_scene() -> tuple[list[tuple[float, float]], list[Building]]:
    """경로 + 경로 서편의 고층 건물 3개(높이 50m)."""
    buildings = [
        _rect(37.49745, 37.49795, 127.02655, 127.02690, 50.0),
        _rect(37.49800, 37.49850, 127.02655, 127.02690, 50.0),
        _rect(37.49855, 37.49905, 127.02655, 127.02690, 50.0),
    ]
    return _ROUTE, buildings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Shelter 그늘 엔진 Phase 0 데모")
    parser.add_argument("--html", help="오후 케이스를 Leaflet HTML 로 저장할 경로")
    parser.add_argument("--date", default="2026-07-15", help="YYYY-MM-DD (기본 한여름)")
    args = parser.parse_args(argv)

    route, buildings = synthetic_scene()
    year, month, day = (int(x) for x in args.date.split("-"))

    print(f"경로: 남북 약 {165}m, 서편 고층(50m) 3동, 날짜 {args.date}")
    print("-" * 52)

    results = {}
    for label, hour in (("아침 08:00", 8), ("정오 12:00", 12), ("오후 16:00", 16)):
        depart = datetime(year, month, day, hour, 0, tzinfo=KST)
        rs = compute_route_shade(route, depart, buildings, spacing_m=10.0)
        results[hour] = rs
        sun0 = rs.samples[0]
        print(
            f"{label}  그늘 {rs.shade_percent:5.1f}%  "
            f"(샘플 {rs.total_count}, 신뢰도 {rs.mean_confidence*100:.0f}%, "
            f"태양고도 {sun0.sun_altitude_deg:4.1f}°, 방위 {sun0.sun_azimuth_deg:5.1f}°)"
        )

    print("-" * 52)
    print("해석: 서편 건물 → 오후(서쪽 태양)에 그늘↑, 아침(동쪽 태양)에 그늘↓ 이면 정상.")

    if args.html:
        from .viz import route_shade_to_html

        out = route_shade_to_html(results[16], args.html, buildings=buildings, title="Shelter 오후 16:00")
        print(f"\nHTML 저장: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
