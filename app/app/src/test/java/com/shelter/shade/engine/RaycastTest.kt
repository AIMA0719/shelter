package com.shelter.shade.engine

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Unit tests for [isPointShaded] and [BuildingIndex].
 *
 * Mirrors Python tests in:
 *   shade-engine/tests/test_raycast.py
 *   shade-engine/tests/test_building_index.py
 *
 * Sun azimuth = 0 (north), altitude = 45 °  → shade threshold = distance × tan(45°) = distance.
 * All geometry uses the local ENU xy plane (metres).
 */
class RaycastTest {

    // -----------------------------------------------------------------------
    // Helper
    // -----------------------------------------------------------------------

    /** Build a square [ProjectedBuilding] centred at (cx, cy) with given half-side and height. */
    private fun square(
        cx: Double, cy: Double, half: Double, height: Double,
        estimated: Boolean = false, osmId: String = "b",
    ): ProjectedBuilding {
        val ring = listOf(
            doubleArrayOf(cx - half, cy - half),
            doubleArrayOf(cx + half, cy - half),
            doubleArrayOf(cx + half, cy + half),
            doubleArrayOf(cx - half, cy + half),
        )
        return ProjectedBuilding(ringXy = ring, heightM = height, heightEstimated = estimated, osmId = osmId)
    }

    // -----------------------------------------------------------------------
    // Basic is_point_shaded tests (mirrors test_raycast.py)
    // -----------------------------------------------------------------------

    /**
     * Tall building (height 30 m) centred at (0, 20) with half=5 → its south
     * face is at y=15. Sun azimuth=0 (north), altitude=45°.
     * Required height = 15 * tan(45) = 15 m  <  30 m  → shaded.
     * Blocker distance should be ~15 m.
     */
    @Test
    fun tallBuildingTowardSunShades() {
        val b = square(0.0, 20.0, 5.0, 30.0)
        val res = isPointShaded(doubleArrayOf(0.0, 0.0), 0.0, 45.0, listOf(b))
        assertTrue("Should be shaded", res.shaded)
        assertEquals("reason should be 'building'", "building", res.reason)
        assertNotNull("blockerDistanceM should not be null", res.blockerDistanceM)
        val dist = res.blockerDistanceM!!
        assertTrue("Blocker distance ~15 m, got $dist", dist > 14.0 && dist < 16.0)
    }

    /**
     * Short building (height 10 m) at y=20: required ≈ 15 m > 10 m → sunny.
     */
    @Test
    fun shortBuildingDoesNotShade() {
        val b = square(0.0, 20.0, 5.0, 10.0)
        val res = isPointShaded(doubleArrayOf(0.0, 0.0), 0.0, 45.0, listOf(b))
        assertFalse("Should not be shaded", res.shaded)
        assertEquals("reason should be 'sunny'", "sunny", res.reason)
    }

    /**
     * Building to the south (y = -20) with sun from the north → ray goes north,
     * never hits the building → sunny.
     */
    @Test
    fun buildingAwayFromSunDoesNotShade() {
        val b = square(0.0, -20.0, 5.0, 50.0)
        val res = isPointShaded(doubleArrayOf(0.0, 0.0), 0.0, 45.0, listOf(b))
        assertFalse("Building behind observer should not shade", res.shaded)
    }

    /**
     * Observer is inside the building → "inside_building".
     */
    @Test
    fun pointInsideBuilding() {
        val b = square(0.0, 0.0, 10.0, 30.0)
        val res = isPointShaded(doubleArrayOf(0.0, 0.0), 0.0, 45.0, listOf(b))
        assertTrue("Should be shaded", res.shaded)
        assertEquals("reason should be 'inside_building'", "inside_building", res.reason)
    }

    /**
     * Sun altitude -5° → below horizon → "sun_below".
     */
    @Test
    fun sunBelowHorizonIsShade() {
        val b = square(0.0, 20.0, 5.0, 30.0)
        val res = isPointShaded(doubleArrayOf(0.0, 0.0), 0.0, -5.0, listOf(b))
        assertTrue("Should be shaded", res.shaded)
        assertEquals("reason should be 'sun_below'", "sun_below", res.reason)
    }

    /**
     * Low sun (10°) means long shadow: building at y=100 with height=30.
     * Distance to south face ≈ 95 m. Required = 95 × tan(10°) ≈ 16.7 m < 30 m → shaded.
     */
    @Test
    fun lowSunLongShadow() {
        val b = square(0.0, 100.0, 5.0, 30.0)
        val res = isPointShaded(doubleArrayOf(0.0, 0.0), 0.0, 10.0, listOf(b), maxDistanceM = 500.0)
        assertTrue("Low sun should allow far building to shade", res.shaded)
    }

    /**
     * Estimated height (16 m) near threshold (~15 m) and within 1.2× threshold (18 m)
     * → confidence < 1.0.
     */
    @Test
    fun estimatedHeightReducesConfidenceNearThreshold() {
        val b = square(0.0, 20.0, 5.0, 16.0, estimated = true)
        val res = isPointShaded(doubleArrayOf(0.0, 0.0), 0.0, 45.0, listOf(b))
        assertTrue("Should be shaded", res.shaded)
        assertTrue("Confidence should be < 1.0, got ${res.confidence}", res.confidence < 1.0)
    }

    // -----------------------------------------------------------------------
    // BuildingIndex tests (mirrors test_building_index.py)
    // -----------------------------------------------------------------------

    private fun squareIdx(cx: Double, cy: Double, half: Double, height: Double): ProjectedBuilding {
        val ring = listOf(
            doubleArrayOf(cx - half, cy - half),
            doubleArrayOf(cx + half, cy - half),
            doubleArrayOf(cx + half, cy + half),
            doubleArrayOf(cx - half, cy + half),
        )
        return ProjectedBuilding(
            ringXy = ring, heightM = height,
            osmId = "$cx,$cy",
        )
    }

    /** 7×7 grid of buildings at 100 m spacing with varying heights. */
    private fun gridOfBuildings(): List<ProjectedBuilding> {
        val list = mutableListOf<ProjectedBuilding>()
        for (i in 0..6) {
            for (j in 0..6) {
                list.add(squareIdx(i * 100.0, j * 100.0, 15.0, 10.0 + (i + j) * 4.0))
            }
        }
        return list
    }

    /**
     * BuildingIndex result must match brute-force isPointShaded for every
     * combination of tested azimuths and sample points.
     */
    @Test
    fun indexMatchesBruteForce() {
        val blds = gridOfBuildings()
        val index = BuildingIndex(blds)
        val azimuths = listOf(0.0, 45.0, 135.0, 200.0, 270.0, 330.0)
        var pxVal = -50
        while (pxVal < 700) {
            var pyVal = -50
            while (pyVal < 700) {
                val point = doubleArrayOf(pxVal.toDouble(), pyVal.toDouble())
                val brute = isPointShaded(point, 0.0, 40.0, blds, maxDistanceM = 300.0)
                val fast = index.isPointShaded(point, 0.0, 40.0, maxDistanceM = 300.0)
                assertEquals(
                    "shaded mismatch at ($pxVal,$pyVal) az=0",
                    brute.shaded, fast.shaded,
                )
                assertEquals(
                    "reason mismatch at ($pxVal,$pyVal) az=0",
                    brute.reason, fast.reason,
                )
                for (az in azimuths) {
                    val b2 = isPointShaded(point, az, 40.0, blds, maxDistanceM = 300.0)
                    val f2 = index.isPointShaded(point, az, 40.0, maxDistanceM = 300.0)
                    assertEquals(
                        "shaded mismatch at ($pxVal,$pyVal) az=$az",
                        b2.shaded, f2.shaded,
                    )
                    assertEquals(
                        "reason mismatch at ($pxVal,$pyVal) az=$az",
                        b2.reason, f2.reason,
                    )
                }
                pyVal += 53
            }
            pxVal += 37
        }
    }

    /**
     * Sun below horizon: BuildingIndex should return "sun_below" immediately.
     */
    @Test
    fun indexSunBelowShortcut() {
        val index = BuildingIndex(gridOfBuildings())
        val res = index.isPointShaded(doubleArrayOf(0.0, 0.0), 180.0, -3.0, maxDistanceM = 300.0)
        assertTrue("Should be shaded", res.shaded)
        assertEquals("sun_below", res.reason)
    }

    /**
     * Empty building list → sunny.
     */
    @Test
    fun indexEmpty() {
        val index = BuildingIndex(emptyList())
        val res = index.isPointShaded(doubleArrayOf(0.0, 0.0), 180.0, 45.0, maxDistanceM = 300.0)
        assertFalse("Should not be shaded", res.shaded)
        assertEquals("sunny", res.reason)
    }
}
