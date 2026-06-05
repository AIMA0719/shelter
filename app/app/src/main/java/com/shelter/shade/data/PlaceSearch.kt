package com.shelter.shade.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.contentOrNull
import okhttp3.OkHttpClient
import okhttp3.Request
import java.util.concurrent.TimeUnit

/**
 * A lightweight place in the result set — name, coordinates, and optional full address.
 */
data class PlaceResult(
    val name: String,
    val lat: Double,
    val lon: Double,
    val address: String? = null,
)

/**
 * Geocoding / reverse-geocoding via OSM Nominatim (free, no API key required).
 *
 * Nominatim ToS requires a valid User-Agent and limits to 1 req/s — callers
 * are responsible for rate-limiting in production.
 *
 * Search endpoint : https://nominatim.openstreetmap.org/search
 * Reverse endpoint: https://nominatim.openstreetmap.org/reverse
 */
object PlaceSearch {

    private const val NOMINATIM_BASE = "https://nominatim.openstreetmap.org"
    private const val USER_AGENT = "shelter-shade-app/0.1 (contact: tech.infocar@gmail.com)"

    /** Shared OkHttpClient with the required User-Agent interceptor. */
    private val client: OkHttpClient by lazy {
        OkHttpClient.Builder()
            .addInterceptor { chain ->
                val request = chain.request().newBuilder()
                    .header("User-Agent", USER_AGENT)
                    .build()
                chain.proceed(request)
            }
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .build()
    }

    // -------------------------------------------------------------------------
    // Public suspend API
    // -------------------------------------------------------------------------

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
            val encodedQuery = java.net.URLEncoder.encode(query, "UTF-8")
            val urlBuilder = StringBuilder(
                "$NOMINATIM_BASE/search" +
                    "?q=$encodedQuery" +
                    "&format=jsonv2" +
                    "&limit=$limit" +
                    "&addressdetails=1" +
                    "&accept-language=ko"
            )
            if (viewbox != null && viewbox.size == 4) {
                // viewbox = [minLon, minLat, maxLon, maxLat]
                urlBuilder.append(
                    "&viewbox=${viewbox[0]},${viewbox[1]},${viewbox[2]},${viewbox[3]}" +
                        "&bounded=1"
                )
            }

            val responseBody = executeGet(urlBuilder.toString()) ?: return@withContext emptyList()
            parseSearchResults(responseBody)
        } catch (e: Exception) {
            emptyList()
        }
    }

    /**
     * Reverse-geocode ([lat], [lon]) → human-readable label.
     *
     * @return The `display_name` string from Nominatim, or null on any error.
     */
    suspend fun reverse(lat: Double, lon: Double): String? = withContext(Dispatchers.IO) {
        try {
            val url = "$NOMINATIM_BASE/reverse" +
                "?lat=$lat" +
                "&lon=$lon" +
                "&format=jsonv2" +
                "&accept-language=ko" +
                "&zoom=18"
            val responseBody = executeGet(url) ?: return@withContext null
            parseReverse(responseBody)
        } catch (e: Exception) {
            null
        }
    }

    // -------------------------------------------------------------------------
    // Internal helpers (called directly by unit tests — no network)
    // -------------------------------------------------------------------------

    /**
     * Parse a Nominatim jsonv2 **search** response (JSON array) into [PlaceResult] objects.
     *
     * - `lat` / `lon` arrive as JSON strings → parsed to Double.
     * - `name` field used as the short name when non-empty; otherwise the first
     *   comma-separated segment of `display_name` is used.
     * - Malformed / missing elements are silently skipped.
     */
    internal fun parseSearchResults(json: String): List<PlaceResult> {
        return try {
            val root = Json.parseToJsonElement(json)
            root.jsonArray.mapNotNull { element ->
                try {
                    val obj = element.jsonObject
                    val latStr = obj["lat"]?.jsonPrimitive?.contentOrNull ?: return@mapNotNull null
                    val lonStr = obj["lon"]?.jsonPrimitive?.contentOrNull ?: return@mapNotNull null
                    val lat = latStr.toDoubleOrNull() ?: return@mapNotNull null
                    val lon = lonStr.toDoubleOrNull() ?: return@mapNotNull null
                    val displayName = obj["display_name"]?.jsonPrimitive?.contentOrNull
                    val rawName = obj["name"]?.jsonPrimitive?.contentOrNull

                    val name = when {
                        !rawName.isNullOrBlank() -> rawName
                        displayName != null -> displayName.split(",").firstOrNull()?.trim() ?: displayName
                        else -> return@mapNotNull null
                    }

                    PlaceResult(
                        name = name,
                        lat = lat,
                        lon = lon,
                        address = displayName,
                    )
                } catch (e: Exception) {
                    null // skip malformed elements
                }
            }
        } catch (e: Exception) {
            emptyList()
        }
    }

    /**
     * Parse a Nominatim jsonv2 **reverse** response (JSON object) and return `display_name`.
     *
     * Returns null when the field is absent or the JSON is malformed.
     */
    internal fun parseReverse(json: String): String? {
        return try {
            val root = Json.parseToJsonElement(json)
            root.jsonObject["display_name"]?.jsonPrimitive?.contentOrNull
        } catch (e: Exception) {
            null
        }
    }

    // -------------------------------------------------------------------------
    // Private network utility
    // -------------------------------------------------------------------------

    /** Execute a GET request and return the response body string, or null on failure. */
    private fun executeGet(url: String): String? {
        val request = Request.Builder().url(url).build()
        val response = client.newCall(request).execute()
        return if (response.isSuccessful) {
            response.body?.string()
        } else {
            response.close()
            null
        }
    }
}
