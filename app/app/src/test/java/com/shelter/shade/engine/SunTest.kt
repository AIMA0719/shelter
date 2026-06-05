package com.shelter.shade.engine

import org.junit.Assert.*
import org.junit.Test
import java.time.LocalDate
import java.time.LocalTime
import java.time.OffsetDateTime
import java.time.ZoneOffset

class SunTest {

    // Seoul geographic coordinates
    private val seoulLat = 37.5665
    private val seoulLon = 126.9780

    // KST = UTC+9
    private val kst = ZoneOffset.ofHours(9)

    /** Build UTC epoch millis from a KST date/time. */
    private fun kstEpoch(year: Int, month: Int, day: Int, hour: Int, minute: Int): Long =
        OffsetDateTime
            .of(LocalDate.of(year, month, day), LocalTime.of(hour, minute), kst)
            .toInstant()
            .toEpochMilli()

    // -----------------------------------------------------------------------
    // Summer solstice — 2026-06-21
    // -----------------------------------------------------------------------

    @Test
    fun `summer solstice max altitude is near theoretical maximum`() {
        // Scan from 05:00 to 20:00 KST every 5 minutes
        val positions = (5 * 60..20 * 60 step 5).map { minOfDay ->
            val h = minOfDay / 60
            val m = minOfDay % 60
            solarPosition(seoulLat, seoulLon, kstEpoch(2026, 6, 21, h, m))
        }
        val maxAlt = positions.maxOf { it.altitudeDeg }

        // Theoretical transit altitude = 90 - lat + obliquity ≈ 90 - 37.5665 + 23.44 ≈ 75.87°
        val theoretical = 90.0 - seoulLat + 23.44
        assertEquals("summer solstice max altitude", theoretical, maxAlt, 2.0)
    }

    @Test
    fun `summer solstice solar noon azimuth is southward (165°–195°)`() {
        // Find the time-step with maximum altitude on summer solstice
        val candidates = (5 * 60..20 * 60 step 5).map { minOfDay ->
            val h = minOfDay / 60
            val m = minOfDay % 60
            solarPosition(seoulLat, seoulLon, kstEpoch(2026, 6, 21, h, m))
        }
        val noonPos = candidates.maxByOrNull { it.altitudeDeg }!!
        assertTrue(
            "solar noon azimuth in south range (165–195), got ${noonPos.azimuthDeg}",
            noonPos.azimuthDeg in 165.0..195.0,
        )
    }

    // -----------------------------------------------------------------------
    // Winter solstice — 2026-12-21
    // -----------------------------------------------------------------------

    @Test
    fun `winter solstice max altitude is near theoretical minimum`() {
        val positions = (6 * 60..18 * 60 step 5).map { minOfDay ->
            val h = minOfDay / 60
            val m = minOfDay % 60
            solarPosition(seoulLat, seoulLon, kstEpoch(2026, 12, 21, h, m))
        }
        val maxAlt = positions.maxOf { it.altitudeDeg }

        // Theoretical = 90 - lat - obliquity ≈ 90 - 37.5665 - 23.44 ≈ 28.99°
        val theoretical = 90.0 - seoulLat - 23.44
        assertEquals("winter solstice max altitude", theoretical, maxAlt, 2.0)
    }

    // -----------------------------------------------------------------------
    // Night-time — 02:00 KST on summer solstice
    // -----------------------------------------------------------------------

    @Test
    fun `sun is below horizon at 02 00 KST`() {
        val pos = solarPosition(seoulLat, seoulLon, kstEpoch(2026, 6, 21, 2, 0))
        assertTrue("altitude < 0 at 02:00 KST, got ${pos.altitudeDeg}", pos.altitudeDeg < 0.0)
        assertFalse("isUp false at 02:00 KST", pos.isUp)
    }

    // -----------------------------------------------------------------------
    // Azimuth direction checks on summer solstice
    // -----------------------------------------------------------------------

    @Test
    fun `afternoon 15 00 KST azimuth is greater than 180`() {
        val pos = solarPosition(seoulLat, seoulLon, kstEpoch(2026, 6, 21, 15, 0))
        assertTrue("afternoon azimuth > 180, got ${pos.azimuthDeg}", pos.azimuthDeg > 180.0)
    }

    @Test
    fun `morning 08 00 KST azimuth is less than 180`() {
        val pos = solarPosition(seoulLat, seoulLon, kstEpoch(2026, 6, 21, 8, 0))
        assertTrue("morning azimuth < 180, got ${pos.azimuthDeg}", pos.azimuthDeg < 180.0)
    }

    // -----------------------------------------------------------------------
    // isUp consistency with altitudeDeg
    // -----------------------------------------------------------------------

    @Test
    fun `isUp is true when altitude is positive and false otherwise`() {
        for (h in 0..23) {
            val pos = solarPosition(seoulLat, seoulLon, kstEpoch(2026, 6, 21, h, 0))
            val expectedIsUp = pos.altitudeDeg > 0.0
            assertEquals("isUp consistent at ${h}:00 KST", expectedIsUp, pos.isUp)
        }
    }

    // -----------------------------------------------------------------------
    // Declination is near ±23.44° on solstices
    // -----------------------------------------------------------------------

    @Test
    fun `summer solstice declination is near +23 44 degrees`() {
        val pos = solarPosition(seoulLat, seoulLon, kstEpoch(2026, 6, 21, 12, 0))
        assertEquals("summer declination ≈ +23.44°", 23.44, pos.declinationDeg, 0.5)
    }

    @Test
    fun `winter solstice declination is near -23 44 degrees`() {
        val pos = solarPosition(seoulLat, seoulLon, kstEpoch(2026, 12, 21, 12, 0))
        assertEquals("winter declination ≈ -23.44°", -23.44, pos.declinationDeg, 0.5)
    }
}
