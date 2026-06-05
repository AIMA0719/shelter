from datetime import datetime, timedelta, timezone

from shade_engine.demo import synthetic_scene
from shade_engine.engine import compute_route_shade, sample_polyline

KST = timezone(timedelta(hours=9))


def test_sample_polyline_spacing_and_endpoints():
    start = (37.5, 127.0)
    end = (37.5 + 0.000898, 127.0)  # 약 100m 북쪽
    samples = sample_polyline([start, end], spacing_m=10.0)
    assert samples[0][2] == 0.0
    assert 95 < samples[-1][2] < 105  # 마지막 누적거리 ≈ 100m
    dists = [s[2] for s in samples]
    assert dists == sorted(dists)  # 단조 증가
    for a, b in zip(dists, dists[1:]):
        assert b - a <= 10.5


def test_sample_polyline_boundary_vertex_not_dropped():
    # 코덱스 회귀: 세그먼트 길이가 spacing 과 정렬될 때 경계 정점이 누락되면 안 됨.
    # 약 10m 짜리 두 구간 + 10m 간격 → 0, 10, 20m 세 샘플 모두 존재해야 한다.
    step = 0.0000898  # 약 10m (위도)
    coords = [(37.5, 127.0), (37.5 + step, 127.0), (37.5 + 2 * step, 127.0)]
    samples = sample_polyline(coords, spacing_m=10.0)
    dists = [round(s[2]) for s in samples]
    assert 10 in dists  # 중간 정점(≈10m)이 살아있어야 함
    assert dists == sorted(dists)
    for a, b in zip(dists, dists[1:]):
        assert b - a <= 11  # 간격이 두 배(20m)로 벌어지지 않음


def test_sample_polyline_single_point():
    assert sample_polyline([(37.5, 127.0)]) == [(37.5, 127.0, 0.0)]


def test_sample_polyline_empty():
    assert sample_polyline([]) == []


def test_route_shade_afternoon_more_than_morning():
    # 서편 고층 → 오후(서쪽 태양) 그늘 > 아침(동쪽 태양) 그늘
    route, buildings = synthetic_scene()
    morning = compute_route_shade(
        route, datetime(2026, 7, 15, 8, 0, tzinfo=KST), buildings, spacing_m=10.0
    )
    afternoon = compute_route_shade(
        route, datetime(2026, 7, 15, 16, 0, tzinfo=KST), buildings, spacing_m=10.0
    )
    assert afternoon.shade_fraction > morning.shade_fraction
    assert afternoon.shade_percent > 50.0  # 오후엔 대체로 그늘


def test_route_shade_fraction_bounds():
    route, buildings = synthetic_scene()
    rs = compute_route_shade(
        route, datetime(2026, 7, 15, 12, 0, tzinfo=KST), buildings, spacing_m=10.0
    )
    assert 0.0 <= rs.shade_fraction <= 1.0
    assert rs.total_count > 0
    assert rs.shaded_count + rs.sunny_count == rs.total_count
