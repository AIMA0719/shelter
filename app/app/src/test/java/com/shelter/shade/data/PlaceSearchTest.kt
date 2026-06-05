package com.shelter.shade.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class PlaceSearchTest {

    // -------------------------------------------------------------------------
    // parseSearchResults
    // -------------------------------------------------------------------------

    @Test
    fun parseSearchResults_twoElements_returnsCorrectPlaceResults() {
        // Element 1: has a non-empty "name" field → name should come from "name"
        // Element 2: no "name" field        → name should be the first comma segment of display_name
        val json = """
            [
              {
                "lat": "37.4975",
                "lon": "127.0270",
                "name": "강남구청",
                "display_name": "강남구청, 학동로, 논현동, 강남구, 서울특별시, 대한민국"
              },
              {
                "lat": "37.5172",
                "lon": "127.0473",
                "display_name": "코엑스, 영동대로, 삼성동, 강남구, 서울특별시, 대한민국"
              }
            ]
        """.trimIndent()

        val results = PlaceSearch.parseSearchResults(json)

        assertEquals(2, results.size)

        // First result: name comes from the "name" field
        val first = results[0]
        assertEquals("강남구청", first.name)
        assertEquals(37.4975, first.lat, 1e-9)
        assertEquals(127.0270, first.lon, 1e-9)
        assertEquals("강남구청, 학동로, 논현동, 강남구, 서울특별시, 대한민국", first.address)

        // Second result: name comes from the first comma segment of display_name
        val second = results[1]
        assertEquals("코엑스", second.name)
        assertEquals(37.5172, second.lat, 1e-9)
        assertEquals(127.0473, second.lon, 1e-9)
        assertEquals("코엑스, 영동대로, 삼성동, 강남구, 서울특별시, 대한민국", second.address)
    }

    @Test
    fun parseSearchResults_emptyArray_returnsEmptyList() {
        val results = PlaceSearch.parseSearchResults("[]")
        assertTrue(results.isEmpty())
    }

    @Test
    fun parseSearchResults_garbageInput_returnsEmptyList_noThrow() {
        val results = PlaceSearch.parseSearchResults("garbage not json {{{{")
        assertTrue(results.isEmpty())
    }

    @Test
    fun parseSearchResults_elementMissingLatLon_elementSkipped() {
        // One valid element, one missing lat → only 1 result
        val json = """
            [
              {
                "lat": "37.4975",
                "lon": "127.0270",
                "name": "강남역",
                "display_name": "강남역, 강남구, 서울특별시, 대한민국"
              },
              {
                "display_name": "위도경도없음"
              }
            ]
        """.trimIndent()

        val results = PlaceSearch.parseSearchResults(json)
        assertEquals(1, results.size)
        assertEquals("강남역", results[0].name)
    }

    @Test
    fun parseSearchResults_emptyNameField_usesFirstCommaSegmentOfDisplayName() {
        // "name" is present but blank → fall back to first comma segment
        val json = """
            [
              {
                "lat": "37.5665",
                "lon": "126.9780",
                "name": "",
                "display_name": "서울특별시청, 세종대로, 태평로1가, 중구, 서울특별시, 대한민국"
              }
            ]
        """.trimIndent()

        val results = PlaceSearch.parseSearchResults(json)
        assertEquals(1, results.size)
        assertEquals("서울특별시청", results[0].name)
    }

    // -------------------------------------------------------------------------
    // parseReverse
    // -------------------------------------------------------------------------

    @Test
    fun parseReverse_validObject_returnsDisplayName() {
        val json = """
            {
              "place_id": 123456,
              "lat": "37.4975",
              "lon": "127.0270",
              "display_name": "강남구청, 학동로, 논현동, 강남구, 서울특별시, 대한민국",
              "address": {
                "suburb": "논현동",
                "city": "서울특별시",
                "country": "대한민국"
              }
            }
        """.trimIndent()

        val result = PlaceSearch.parseReverse(json)
        assertEquals("강남구청, 학동로, 논현동, 강남구, 서울특별시, 대한민국", result)
    }

    @Test
    fun parseReverse_emptyObject_returnsNull() {
        val result = PlaceSearch.parseReverse("{}")
        assertNull(result)
    }

    @Test
    fun parseReverse_garbageInput_returnsNull_noThrow() {
        val result = PlaceSearch.parseReverse("garbage not json {{{{")
        assertNull(result)
    }
}
