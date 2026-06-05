from datetime import datetime, timedelta, timezone

from shade_engine.sun import solar_position

SEOUL = (37.5665, 126.9780)
KST = timezone(timedelta(hours=9))


def _max_altitude_of_day(date, lat, lon):
    best = None
    best_pos = None
    for minutes in range(0, 24 * 60, 5):
        dt = datetime(date.year, date.month, date.day, tzinfo=KST) + timedelta(minutes=minutes)
        pos = solar_position(lat, lon, dt)
        if best is None or pos.altitude_deg > best:
            best = pos.altitude_deg
            best_pos = pos
    return best, best_pos


def test_summer_solstice_noon_altitude():
    # 하지 정오 최대고도 ≈ 90 - 위도 + 23.44
    expected = 90 - SEOUL[0] + 23.44
    alt, pos = _max_altitude_of_day(datetime(2026, 6, 21), *SEOUL)
    assert abs(alt - expected) < 2.0
    # 최대 고도 시각엔 태양이 남쪽(방위 ~180)
    assert 165 < pos.azimuth_deg < 195


def test_winter_solstice_noon_altitude():
    expected = 90 - SEOUL[0] - 23.44
    alt, _ = _max_altitude_of_day(datetime(2026, 12, 21), *SEOUL)
    assert abs(alt - expected) < 2.0


def test_night_is_down():
    # 한밤중(02:00 KST)엔 태양이 지평선 아래
    dt = datetime(2026, 7, 15, 2, 0, tzinfo=KST)
    pos = solar_position(*SEOUL, dt)
    assert pos.altitude_deg < 0
    assert pos.is_up is False


def test_azimuth_range_and_declination():
    dt = datetime(2026, 7, 15, 15, 0, tzinfo=KST)
    pos = solar_position(*SEOUL, dt)
    assert 0.0 <= pos.azimuth_deg < 360.0
    assert -23.5 <= pos.declination_deg <= 23.5
    # 오후엔 태양이 서쪽(방위 > 180)
    assert pos.azimuth_deg > 180


def test_morning_sun_in_east():
    dt = datetime(2026, 7, 15, 8, 0, tzinfo=KST)
    pos = solar_position(*SEOUL, dt)
    assert pos.altitude_deg > 0
    assert pos.azimuth_deg < 180  # 동쪽
