package com.shelter.shade.engine

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate
import java.time.LocalTime
import java.time.OffsetDateTime
import java.time.ZoneOffset

class RoutingTest {

    // 동서로 떨어진 두 남북 거리 + 상하 연결로 (Python test_osm_routing 와 동일 구조)
    private val twoStreetGeoJson = """
    {"type":"FeatureCollection","features":[
      {"type":"Feature","properties":{"highway":"footway"},"geometry":{"type":"LineString","coordinates":[[127.0271,37.49750],[127.0271,37.49800],[127.0271,37.49850],[127.0271,37.49900]]}},
      {"type":"Feature","properties":{"highway":"footway"},"geometry":{"type":"LineString","coordinates":[[127.0276,37.49750],[127.0276,37.49800],[127.0276,37.49850],[127.0276,37.49900]]}},
      {"type":"Feature","properties":{"highway":"footway"},"geometry":{"type":"LineString","coordinates":[[127.0271,37.49750],[127.0276,37.49750]]}},
      {"type":"Feature","properties":{"highway":"footway"},"geometry":{"type":"LineString","coordinates":[[127.0271,37.49900],[127.0276,37.49900]]}}
    ]}
    """.trimIndent()

    private fun westBuildings() = listOf(
        Building(
            ring = listOf(
                doubleArrayOf(37.49745, 127.02655), doubleArrayOf(37.49745, 127.02690),
                doubleArrayOf(37.49905, 127.02690), doubleArrayOf(37.49905, 127.02655),
            ),
            heightM = 50.0,
        ),
    )

    private fun afternoonSun(lat: Double, lon: Double): SolarPosition {
        val e = OffsetDateTime.of(LocalDate.of(2026, 7, 15), LocalTime.of(16, 0), ZoneOffset.ofHours(9))
            .toInstant().toEpochMilli()
        return solarPosition(lat, lon, e)
    }

    @Test
    fun graphParses() {
        val g = OsmGraph.fromGeoJson(twoStreetGeoJson)
        assertTrue(g.nodeCount() >= 8)
        assertTrue(g.edgeCount() >= 8)
    }

    @Test
    fun planRoutesInvariants() {
        val g = OsmGraph.fromGeoJson(twoStreetGeoJson)
        val origin = doubleArrayOf(37.49750, 127.0271)
        val dest = doubleArrayOf(37.49900, 127.0271)
        val sun = afternoonSun(origin[0], origin[1])
        val opts = planRoutesOsm(g, origin, dest, westBuildings(), sun.azimuthDeg, sun.altitudeDeg)
        assertEquals(setOf("shortest", "balanced", "shadiest"), opts.map { it.name }.toSet())
        for (o in opts) {
            assertEquals(origin[0], o.coords.first()[0], 1e-9)
            assertEquals(dest[0], o.coords.last()[0], 1e-9)
            assertTrue(o.sunFraction in 0.0..1.0)
        }
        val by = opts.associateBy { it.name }
        // 그늘 최적은 최단보다 햇빛이 더 많지 않다
        assertTrue(by["shadiest"]!!.sunFraction <= by["shortest"]!!.sunFraction + 1e-9)
    }

    @Test
    fun outsideNetworkThrows() {
        val g = OsmGraph.fromGeoJson(twoStreetGeoJson)
        assertThrows(RouteNotFoundException::class.java) {
            planRoutesOsm(g, doubleArrayOf(37.6, 127.2), doubleArrayOf(37.61, 127.2), emptyList(), 264.0, 44.0)
        }
    }

    @Test
    fun sameNodeRouteKeepsBothEndpoints() {
        // 코덱스 회귀: 출발·도착이 같은 노드로 스냅돼도 좌표가 1개로 뭉개지면 안 됨.
        val g = OsmGraph.fromGeoJson(twoStreetGeoJson)
        val origin = doubleArrayOf(37.49750, 127.0271)
        val dest = doubleArrayOf(37.497505, 127.0271) // ~0.5m → 같은 노드 스냅
        val sun = afternoonSun(origin[0], origin[1])
        val opts = planRoutesOsm(g, origin, dest, westBuildings(), sun.azimuthDeg, sun.altitudeDeg)
        for (o in opts) {
            assertTrue("coords >= 2", o.coords.size >= 2)
            assertEquals(origin[0], o.coords.first()[0], 1e-9)
            assertEquals(dest[0], o.coords.last()[0], 1e-9)
        }
    }

    @Test
    fun preferSunRenamesOption() {
        val g = OsmGraph.fromGeoJson(twoStreetGeoJson)
        val sun = afternoonSun(37.49750, 127.0271)
        val opts = planRoutesOsm(
            g, doubleArrayOf(37.49750, 127.0271), doubleArrayOf(37.49900, 127.0271),
            westBuildings(), sun.azimuthDeg, sun.altitudeDeg, preferSun = true,
        )
        assertTrue(opts.any { it.name == "sunniest" })
    }
}
