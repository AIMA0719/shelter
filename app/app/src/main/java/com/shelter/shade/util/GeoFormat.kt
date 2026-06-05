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
}
