package com.shelter.shade.util

import com.shelter.shade.data.LatLng

/** Android 런타임 없이 단위 테스트 가능한 순수 좌표 파싱/검증 유틸. */
object GeoFormat {

    fun parseLatLng(lat: String, lon: String): LatLng? {
        val la = lat.trim().toDoubleOrNull() ?: return null
        val lo = lon.trim().toDoubleOrNull() ?: return null
        if (la < -90.0 || la > 90.0) return null
        if (lo < -180.0 || lo > 180.0) return null
        return LatLng(la, lo)
    }

    /** 거리(m) → 사람이 읽기 좋은 표기. 1km 이상은 'x.xkm', 미만은 'NNNm'. */
    fun distance(meters: Double): String =
        if (meters >= 1000.0) "%.1fkm".format(meters / 1000.0) else "${meters.toInt()}m"

    /** 예상 소요시간(분) → '약 N분' / '약 H시간 M분'. */
    fun duration(minutes: Double): String {
        val m = Math.round(minutes).toInt().coerceAtLeast(1)
        if (m < 60) return "약 ${m}분"
        val h = m / 60
        val rem = m % 60
        return if (rem == 0) "약 ${h}시간" else "약 ${h}시간 ${rem}분"
    }
}
