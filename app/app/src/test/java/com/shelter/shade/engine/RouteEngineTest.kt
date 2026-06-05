package com.shelter.shade.engine

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate
import java.time.LocalTime
import java.time.OffsetDateTime
import java.time.ZoneOffset

class RouteEngineTest {

    private val kst = ZoneOffset.ofHours(9)

    private fun epoch(h: Int): Long =
        OffsetDateTime.of(LocalDate.of(2026, 7, 15), LocalTime.of(h, 0), kst).toInstant().toEpochMilli()

    private fun rect(minLat: Double, maxLat: Double, minLon: Double, maxLon: Double, height: Double) =
        Building(
            ring = listOf(
                doubleArrayOf(minLat, minLon),
                doubleArrayOf(minLat, maxLon),
                doubleArrayOf(maxLat, maxLon),
                doubleArrayOf(maxLat, minLon),
            ),
            heightM = height,
        )

    // shade-engine 의 synthetic_scene 과 동일: 경로 서편 고층(50m) 3동
    private fun scene(): Pair<List<DoubleArray>, List<Building>> {
        val route = (0..10).map { doubleArrayOf(37.49750 + it * 0.00015, 127.0270) }
        val buildings = listOf(
            rect(37.49745, 37.49795, 127.02655, 127.02690, 50.0),
            rect(37.49800, 37.49850, 127.02655, 127.02690, 50.0),
            rect(37.49855, 37.49905, 127.02655, 127.02690, 50.0),
        )
        return route to buildings
    }

    @Test
    fun afternoonMoreShadeThanMorning() {
        val (route, buildings) = scene()
        val morning = computeRouteShade(route, epoch(8), buildings, spacingM = 10.0)
        val afternoon = computeRouteShade(route, epoch(16), buildings, spacingM = 10.0)
        // 서편 건물 → 오후(서쪽 태양)에 그늘↑, 아침(동쪽 태양)에 그늘↓
        assertTrue("afternoon ${afternoon.shadePercent} > morning ${morning.shadePercent}",
            afternoon.shadeFraction > morning.shadeFraction)
        assertTrue("afternoon ${afternoon.shadePercent} > 50", afternoon.shadePercent > 50.0)
    }

    @Test
    fun shadeFractionBounds() {
        val (route, buildings) = scene()
        val rs = computeRouteShade(route, epoch(12), buildings, spacingM = 10.0)
        assertTrue(rs.shadeFraction in 0.0..1.0)
        assertTrue(rs.totalCount > 0)
        assertEquals(rs.totalCount, rs.shadedCount + rs.sunnyCount)
    }

    @Test
    fun samplePolylineEndpoints() {
        val coords = listOf(doubleArrayOf(37.5, 127.0), doubleArrayOf(37.5 + 0.000898, 127.0)) // ~100m
        val s = samplePolyline(coords, 10.0)
        assertEquals(0.0, s.first()[2], 1e-9)
        assertTrue(s.last()[2] in 95.0..105.0)
        for (i in 0 until s.size - 1) assertTrue(s[i + 1][2] - s[i][2] <= 10.5)
    }
}
