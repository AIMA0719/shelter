package com.shelter.shade.engine

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Unit tests for [estimateHeightM] and [loadGeoJson].
 *
 * Mirrors expected behaviour from the Python buildings module and covers the
 * GeoJSON round-trip requirement (loadGeoJson on an inline FeatureCollection).
 */
class BuildingsTest {

    // -----------------------------------------------------------------------
    // estimateHeightM
    // -----------------------------------------------------------------------

    @Test
    fun heightTagParsedDirectly() {
        val (h, est) = estimateHeightM(mapOf("height" to "12.5"))
        assertEquals(12.5, h, 0.001)
        assertEquals(false, est)
    }

    @Test
    fun heightTagWithMSuffix() {
        val (h, est) = estimateHeightM(mapOf("height" to "10m"))
        assertEquals(10.0, h, 0.001)
        assertEquals(false, est)
    }

    @Test
    fun heightTagWithMetersWord() {
        val (h, est) = estimateHeightM(mapOf("height" to "8 meters"))
        assertEquals(8.0, h, 0.001)
        assertEquals(false, est)
    }

    @Test
    fun buildingLevelsFallback() {
        val (h, est) = estimateHeightM(mapOf("building:levels" to "5"))
        assertEquals(15.0, h, 0.001)   // 5 × 3.0
        assertEquals(true, est)
    }

    @Test
    fun levelsTagFallback() {
        val (h, est) = estimateHeightM(mapOf("levels" to "3"))
        assertEquals(9.0, h, 0.001)
        assertEquals(true, est)
    }

    @Test
    fun defaultHeightWhenNoTags() {
        val (h, est) = estimateHeightM(emptyMap())
        assertEquals(DEFAULT_BUILDING_HEIGHT_M, h, 0.001)
        assertEquals(true, est)
    }

    @Test
    fun invalidHeightTagFallsBackToLevels() {
        val (h, est) = estimateHeightM(mapOf("height" to "n/a", "building:levels" to "4"))
        assertEquals(12.0, h, 0.001)   // 4 × 3.0
        assertEquals(true, est)
    }

    @Test
    fun zeroHeightTagIgnored() {
        // "0" parses as 0 which is non-positive → fall through to levels
        val (h, est) = estimateHeightM(mapOf("height" to "0", "building:levels" to "2"))
        assertEquals(6.0, h, 0.001)
        assertEquals(true, est)
    }

    // -----------------------------------------------------------------------
    // loadGeoJson — Polygon with building:levels=5
    // -----------------------------------------------------------------------

    private val GEOJSON_ONE_BUILDING = """
        {
          "type": "FeatureCollection",
          "features": [
            {
              "type": "Feature",
              "id": "way/123",
              "geometry": {
                "type": "Polygon",
                "coordinates": [
                  [
                    [127.001, 37.501],
                    [127.002, 37.501],
                    [127.002, 37.502],
                    [127.001, 37.502],
                    [127.001, 37.501]
                  ]
                ]
              },
              "properties": {
                "building": "yes",
                "building:levels": "5"
              }
            }
          ]
        }
    """.trimIndent()

    @Test
    fun loadGeoJsonReturnsSingleBuilding() {
        val buildings = loadGeoJson(GEOJSON_ONE_BUILDING)
        assertEquals("Should parse exactly one building", 1, buildings.size)
    }

    @Test
    fun loadGeoJsonCorrectHeight() {
        val b = loadGeoJson(GEOJSON_ONE_BUILDING).first()
        assertEquals("height should be 5 × 3 = 15 m", 15.0, b.heightM, 0.001)
        assertTrue("height should be flagged as estimated", b.heightEstimated)
    }

    @Test
    fun loadGeoJsonRingHasEnoughPoints() {
        val b = loadGeoJson(GEOJSON_ONE_BUILDING).first()
        assertTrue("ring should have ≥ 3 points, got ${b.ring.size}", b.ring.size >= 3)
    }

    @Test
    fun loadGeoJsonCoordsSwappedToLatLon() {
        // GeoJSON uses [lon, lat]; Buildings.kt must swap to (lat, lon).
        // First coordinate in GeoJSON: [127.001, 37.501]  → lat=37.501, lon=127.001
        val b = loadGeoJson(GEOJSON_ONE_BUILDING).first()
        val firstPt = b.ring.first()
        assertEquals("first element of pair should be lat (37.xxx)", 37.501, firstPt[0], 1e-6)
        assertEquals("second element of pair should be lon (127.xxx)", 127.001, firstPt[1], 1e-6)
    }

    @Test
    fun loadGeoJsonOsmIdFromFeatureId() {
        // The feature has "id": "way/123" at the top level (properties has no "id")
        val b = loadGeoJson(GEOJSON_ONE_BUILDING).first()
        assertEquals("way/123", b.osmId)
    }

    // -----------------------------------------------------------------------
    // loadGeoJson — MultiPolygon (two polygons → two buildings)
    // -----------------------------------------------------------------------

    private val GEOJSON_MULTI_POLYGON = """
        {
          "type": "FeatureCollection",
          "features": [
            {
              "type": "Feature",
              "geometry": {
                "type": "MultiPolygon",
                "coordinates": [
                  [
                    [
                      [127.001, 37.501],
                      [127.002, 37.501],
                      [127.002, 37.502],
                      [127.001, 37.501]
                    ]
                  ],
                  [
                    [
                      [127.003, 37.503],
                      [127.004, 37.503],
                      [127.004, 37.504],
                      [127.003, 37.503]
                    ]
                  ]
                ]
              },
              "properties": {
                "height": "20"
              }
            }
          ]
        }
    """.trimIndent()

    @Test
    fun loadGeoJsonMultiPolygonYieldsTwoBuildings() {
        val buildings = loadGeoJson(GEOJSON_MULTI_POLYGON)
        assertEquals("MultiPolygon with 2 polys → 2 buildings", 2, buildings.size)
    }

    @Test
    fun loadGeoJsonMultiPolygonHeightNotEstimated() {
        val buildings = loadGeoJson(GEOJSON_MULTI_POLYGON)
        for (b in buildings) {
            assertEquals(20.0, b.heightM, 0.001)
            assertEquals(false, b.heightEstimated)
        }
    }

    // -----------------------------------------------------------------------
    // loadGeoJson — ring with < 3 points is skipped
    // -----------------------------------------------------------------------

    private val GEOJSON_DEGENERATE_RING = """
        {
          "type": "FeatureCollection",
          "features": [
            {
              "type": "Feature",
              "geometry": {
                "type": "Polygon",
                "coordinates": [
                  [
                    [127.001, 37.501],
                    [127.002, 37.501]
                  ]
                ]
              },
              "properties": {}
            }
          ]
        }
    """.trimIndent()

    @Test
    fun loadGeoJsonSkipsDegenerateRing() {
        val buildings = loadGeoJson(GEOJSON_DEGENERATE_RING)
        assertTrue("Ring with < 3 points should be skipped", buildings.isEmpty())
    }

    // -----------------------------------------------------------------------
    // Building.bbox()
    // -----------------------------------------------------------------------

    @Test
    fun buildingBboxCorrect() {
        val ring = listOf(
            doubleArrayOf(37.5, 127.0),
            doubleArrayOf(37.6, 127.0),
            doubleArrayOf(37.6, 127.1),
            doubleArrayOf(37.5, 127.1),
        )
        val b = Building(ring = ring, heightM = 10.0)
        val bb = b.bbox()
        assertEquals(37.5, bb[0], 1e-9)
        assertEquals(127.0, bb[1], 1e-9)
        assertEquals(37.6, bb[2], 1e-9)
        assertEquals(127.1, bb[3], 1e-9)
    }

    // -----------------------------------------------------------------------
    // Null / empty input
    // -----------------------------------------------------------------------

    @Test
    fun loadGeoJsonEmptyFeatureCollection() {
        val result = loadGeoJson("""{"type":"FeatureCollection","features":[]}""")
        assertTrue(result.isEmpty())
    }

    @Test
    fun osmIdNullWhenAbsent() {
        val buildings = loadGeoJson("""
            {
              "type": "FeatureCollection",
              "features": [
                {
                  "type": "Feature",
                  "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                      [
                        [127.001, 37.501],
                        [127.002, 37.501],
                        [127.002, 37.502],
                        [127.001, 37.501]
                      ]
                    ]
                  },
                  "properties": {}
                }
              ]
            }
        """.trimIndent())
        assertNull("osmId should be null when no id present", buildings.firstOrNull()?.osmId)
    }
}
