package com.shelter.shade.data

import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.Json
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class PlaceSearchTest {

    /** Fake backend API — geocode calls are overridable, the rest are unused. */
    private open class FakeApi : ShadeApi {
        var lastQuery: String? = null
        var lastViewbox: String? = null
        var searchResponse = GeocodeSearchResponse(results = emptyList())
        var reverseResponse = GeocodeReverseResponse(label = null)

        override suspend fun geocodeSearch(query: String, limit: Int, viewbox: String?): GeocodeSearchResponse {
            lastQuery = query
            lastViewbox = viewbox
            return searchResponse
        }

        override suspend fun geocodeReverse(lat: Double, lon: Double): GeocodeReverseResponse = reverseResponse

        override suspend fun computeShade(request: ShadeRequest): ShadeResponse = throw NotImplementedError()
        override suspend fun planRoutes(request: RoutesRequest): RoutesResponse = throw NotImplementedError()
        override suspend fun suggestDeparture(request: DepartureSuggestRequest): DepartureSuggestResponse =
            throw NotImplementedError()
        override suspend fun getPois(minLat: Double, minLon: Double, maxLat: Double, maxLon: Double): PoisResponse =
            throw NotImplementedError()
    }

    @After
    fun tearDown() {
        PlaceSearch.api = null
    }

    // -------------------------------------------------------------------------
    // search / reverse — backend proxy delegation
    // -------------------------------------------------------------------------

    @Test
    fun search_mapsBackendResultsToPlaceResults() = runBlocking {
        val fake = FakeApi().apply {
            searchResponse = GeocodeSearchResponse(
                results = listOf(
                    GeocodePlace("강남구청", 37.4975, 127.0270, "강남구청, 학동로, 강남구"),
                    GeocodePlace("코엑스", 37.5172, 127.0473, null),
                ),
            )
        }
        PlaceSearch.api = fake

        val results = PlaceSearch.search("강남", viewbox = doubleArrayOf(126.76, 37.41, 127.18, 37.70))

        assertEquals(2, results.size)
        assertEquals(PlaceResult("강남구청", 37.4975, 127.0270, "강남구청, 학동로, 강남구"), results[0])
        assertNull(results[1].address)
        assertEquals("강남", fake.lastQuery)
        assertEquals("126.76,37.41,127.18,37.7", fake.lastViewbox)
    }

    @Test
    fun search_apiThrows_returnsEmptyList_noThrow() = runBlocking {
        PlaceSearch.api = object : FakeApi() {
            override suspend fun geocodeSearch(query: String, limit: Int, viewbox: String?): GeocodeSearchResponse =
                throw RuntimeException("backend down")
        }
        assertTrue(PlaceSearch.search("강남").isEmpty())
    }

    @Test
    fun reverse_returnsBackendLabel() = runBlocking {
        PlaceSearch.api = FakeApi().apply {
            reverseResponse = GeocodeReverseResponse(label = "강남구청, 학동로, 강남구")
        }
        assertEquals("강남구청, 학동로, 강남구", PlaceSearch.reverse(37.4975, 127.0270))
    }

    @Test
    fun reverse_apiThrows_returnsNull_noThrow() = runBlocking {
        PlaceSearch.api = object : FakeApi() {
            override suspend fun geocodeReverse(lat: Double, lon: Double): GeocodeReverseResponse =
                throw RuntimeException("backend down")
        }
        assertNull(PlaceSearch.reverse(37.4975, 127.0270))
    }

    // -------------------------------------------------------------------------
    // formatViewbox
    // -------------------------------------------------------------------------

    @Test
    fun formatViewbox_fourElements_joinsWithCommas() {
        assertEquals("126.76,37.41,127.18,37.7", PlaceSearch.formatViewbox(doubleArrayOf(126.76, 37.41, 127.18, 37.70)))
    }

    @Test
    fun formatViewbox_nullOrWrongSize_returnsNull() {
        assertNull(PlaceSearch.formatViewbox(null))
        assertNull(PlaceSearch.formatViewbox(doubleArrayOf(1.0, 2.0, 3.0)))
    }

    // -------------------------------------------------------------------------
    // DTO deserialization — mirrors NetworkModule's Json config
    // -------------------------------------------------------------------------

    private val json = Json {
        ignoreUnknownKeys = true
        explicitNulls = false
    }

    @Test
    fun geocodeSearchResponse_decodesBackendJson() {
        val body = """
            {"results":[
              {"name":"강남구청","lat":37.4975,"lon":127.027,"address":"강남구청, 학동로, 강남구"},
              {"name":"코엑스","lat":37.5172,"lon":127.0473,"address":null}
            ]}
        """.trimIndent()

        val decoded = json.decodeFromString<GeocodeSearchResponse>(body)
        assertEquals(2, decoded.results.size)
        assertEquals("강남구청", decoded.results[0].name)
        assertEquals(37.4975, decoded.results[0].lat, 1e-9)
        assertNull(decoded.results[1].address)
    }

    @Test
    fun geocodeReverseResponse_decodesNullLabel() {
        assertNull(json.decodeFromString<GeocodeReverseResponse>("{\"label\":null}").label)
        assertNull(json.decodeFromString<GeocodeReverseResponse>("{}").label)
        assertEquals("라벨", json.decodeFromString<GeocodeReverseResponse>("{\"label\":\"라벨\"}").label)
    }
}
