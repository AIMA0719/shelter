package com.shelter.shade.util

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class GeoFormatTest {

    @Test
    fun parsesValidCoordinates() {
        val ll = GeoFormat.parseLatLng(" 37.4975 ", "127.0270")
        assertEquals(37.4975, ll!!.lat, 1e-9)
        assertEquals(127.0270, ll.lon, 1e-9)
    }

    @Test
    fun rejectsNonNumeric() {
        assertNull(GeoFormat.parseLatLng("abc", "127.0"))
    }

    @Test
    fun rejectsOutOfRange() {
        assertNull(GeoFormat.parseLatLng("200", "127.0")) // 위도 범위 밖
        assertNull(GeoFormat.parseLatLng("37.5", "999")) // 경도 범위 밖
    }
}
