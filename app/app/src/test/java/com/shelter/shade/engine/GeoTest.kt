package com.shelter.shade.engine

import org.junit.Assert.*
import org.junit.Test

class GeoTest {

    // -----------------------------------------------------------------------
    // LocalProjection — round-trip
    // -----------------------------------------------------------------------

    @Test
    fun `toXy then toLatLon returns original coordinates`() {
        val proj = LocalProjection(lat0 = 37.5665, lon0 = 126.9780)
        val lat = 37.5700
        val lon = 126.9820

        val xy = proj.toXy(lat, lon)
        val back = proj.toLatLon(xy[0], xy[1])

        assertEquals("lat round-trip", lat, back[0], 1e-9)
        assertEquals("lon round-trip", lon, back[1], 1e-9)
    }

    // -----------------------------------------------------------------------
    // LocalProjection — axes
    // -----------------------------------------------------------------------

    @Test
    fun `point due east produces positive x and near-zero y`() {
        val proj = LocalProjection(lat0 = 0.0, lon0 = 0.0)
        // 1 degree east at equator
        val xy = proj.toXy(0.0, 1.0)
        assertTrue("x > 0 for east point", xy[0] > 0.0)
        assertEquals("y ≈ 0 for east point", 0.0, xy[1], 1e-6)
    }

    @Test
    fun `point due north produces positive y and near-zero x`() {
        val proj = LocalProjection(lat0 = 0.0, lon0 = 0.0)
        // 1 degree north
        val xy = proj.toXy(1.0, 0.0)
        assertTrue("y > 0 for north point", xy[1] > 0.0)
        assertEquals("x ≈ 0 for north point", 0.0, xy[0], 1e-6)
    }

    // -----------------------------------------------------------------------
    // haversineM
    // -----------------------------------------------------------------------

    @Test
    fun `haversineM for 1 degree latitude is within expected range`() {
        // 1 degree of latitude ≈ 111 km (WGS84 varies from ~110.6 to ~111.7 km)
        val dist = haversineM(0.0, 0.0, 1.0, 0.0)
        assertTrue("distance >= 111000 m", dist >= 111_000.0)
        assertTrue("distance <= 111400 m", dist <= 111_400.0)
    }

    @Test
    fun `haversineM is symmetric`() {
        val d1 = haversineM(37.5665, 126.9780, 37.5800, 127.0000)
        val d2 = haversineM(37.5800, 127.0000, 37.5665, 126.9780)
        assertEquals("haversineM symmetric", d1, d2, 1e-6)
    }

    @Test
    fun `haversineM of same point is zero`() {
        assertEquals("zero distance", 0.0, haversineM(37.5665, 126.9780, 37.5665, 126.9780), 1e-6)
    }

    // -----------------------------------------------------------------------
    // bearingDeg
    // -----------------------------------------------------------------------

    @Test
    fun `bearing due north is 0`() {
        val b = bearingDeg(0.0, 0.0, 1.0, 0.0)
        assertEquals("north bearing ≈ 0", 0.0, b, 0.5)
    }

    @Test
    fun `bearing due east is 90`() {
        val b = bearingDeg(0.0, 0.0, 0.0, 1.0)
        assertEquals("east bearing ≈ 90", 90.0, b, 0.5)
    }

    @Test
    fun `bearing due south is 180`() {
        val b = bearingDeg(1.0, 0.0, 0.0, 0.0)
        assertEquals("south bearing ≈ 180", 180.0, b, 0.5)
    }

    @Test
    fun `bearing due west is 270`() {
        val b = bearingDeg(0.0, 1.0, 0.0, 0.0)
        assertEquals("west bearing ≈ 270", 270.0, b, 0.5)
    }

    @Test
    fun `bearing is in range 0 to 360`() {
        val b = bearingDeg(37.5665, 126.9780, 35.6762, 139.6503) // Seoul → Tokyo
        assertTrue("bearing >= 0", b >= 0.0)
        assertTrue("bearing < 360", b < 360.0)
    }
}
