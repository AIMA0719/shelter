package com.shelter.shade.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable

/**
 * A lightweight place in the result set — name, coordinates, and optional full address.
 *
 * `@Serializable` 이므로 즐겨찾기·최근검색 목록을 DataStore 에 JSON 으로 직렬화할 수 있다([UserPrefs]).
 */
@Serializable
data class PlaceResult(
    val name: String,
    val lat: Double,
    val lon: Double,
    val address: String? = null,
)

/**
 * Geocoding / reverse-geocoding via the backend proxy (`/v1/geocode/search|reverse`).
 *
 * The app used to call OSM Nominatim directly, but Nominatim's ToS (valid
 * User-Agent, 1 req/s, caching) cannot be enforced from thousands of client
 * IPs — the backend proxies a single throttled, cached egress instead.
 * Parsing of the Nominatim response now lives server-side.
 */
object PlaceSearch {

    /** Injectable for unit tests (no network). Defaults to the shared Retrofit API. */
    internal var api: ShadeApi? = null

    private fun resolveApi(): ShadeApi = api ?: NetworkModule.shadeApi

    /**
     * Forward-geocode [query] → list of [PlaceResult].
     *
     * @param viewbox Optional bounding box [minLon, minLat, maxLon, maxLat] to bias results.
     * @param limit   Maximum number of results (default 8).
     * @return Matching places, or an empty list on any error.
     */
    suspend fun search(
        query: String,
        viewbox: DoubleArray? = null,
        limit: Int = 8,
    ): List<PlaceResult> = withContext(Dispatchers.IO) {
        try {
            resolveApi()
                .geocodeSearch(query = query, limit = limit, viewbox = formatViewbox(viewbox))
                .results
                .map { it.toPlaceResult() }
        } catch (e: Exception) {
            emptyList()
        }
    }

    /**
     * Reverse-geocode ([lat], [lon]) → human-readable label.
     *
     * @return The label from the backend (Nominatim `display_name`), or null on any error.
     */
    suspend fun reverse(lat: Double, lon: Double): String? = withContext(Dispatchers.IO) {
        try {
            resolveApi().geocodeReverse(lat = lat, lon = lon).label
        } catch (e: Exception) {
            null
        }
    }

    // -------------------------------------------------------------------------
    // Internal helpers (called directly by unit tests — no network)
    // -------------------------------------------------------------------------

    /** Format [minLon, minLat, maxLon, maxLat] as the `viewbox` query param, or null. */
    internal fun formatViewbox(viewbox: DoubleArray?): String? =
        if (viewbox != null && viewbox.size == 4) viewbox.joinToString(",") else null

    internal fun GeocodePlace.toPlaceResult(): PlaceResult =
        PlaceResult(name = name, lat = lat, lon = lon, address = address)
}
