package com.shelter.shade.engine

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const val DEFAULT_LEVEL_HEIGHT_M = 3.0   // metres per floor
const val DEFAULT_BUILDING_HEIGHT_M = 9.0 // fallback when no height/levels tag

// ---------------------------------------------------------------------------
// Data model
// ---------------------------------------------------------------------------

/**
 * Building footprint (lat/lon polygon) and height.
 *
 * [ring] elements are doubleArrayOf(lat, lon) — GeoJSON [lon,lat] is swapped
 * on load so that callers always work in (lat, lon) order.
 * [heightM]          ground-to-roof height in metres.
 * [heightEstimated]  true when height was inferred from levels or default.
 */
data class Building(
    val ring: List<DoubleArray>,
    val heightM: Double,
    val heightEstimated: Boolean = false,
    val osmId: String? = null,
) {
    /**
     * Returns [minLat, minLon, maxLat, maxLon].
     */
    fun bbox(): DoubleArray {
        var minLat = Double.MAX_VALUE
        var minLon = Double.MAX_VALUE
        var maxLat = -Double.MAX_VALUE
        var maxLon = -Double.MAX_VALUE
        for (pt in ring) {
            if (pt[0] < minLat) minLat = pt[0]
            if (pt[1] < minLon) minLon = pt[1]
            if (pt[0] > maxLat) maxLat = pt[0]
            if (pt[1] > maxLon) maxLon = pt[1]
        }
        return doubleArrayOf(minLat, minLon, maxLat, maxLon)
    }
}

// ---------------------------------------------------------------------------
// Height estimation
// ---------------------------------------------------------------------------

/**
 * Parse an OSM `height` tag value that may look like "12", "12 m", "12.5m",
 * "12 meters", "12 metres". Returns the float value in metres, or null if the
 * string cannot be parsed or is non-positive.
 */
private fun parseMeters(value: String): Double? {
    val s = value
        .trim()
        .lowercase()
        .replace("meters", "")
        .replace("metres", "")
        .replace("m", "")
        .trim()
    return try {
        val v = s.toDouble()
        if (v > 0) v else null
    } catch (_: NumberFormatException) {
        null
    }
}

/**
 * Estimate building height from OSM tags.
 *
 * Priority: `height` tag → `building:levels` / `levels` × [DEFAULT_LEVEL_HEIGHT_M]
 *           → [DEFAULT_BUILDING_HEIGHT_M].
 *
 * Returns Pair(heightM, estimated) where *estimated* is false only when a
 * concrete `height` tag was successfully parsed.
 */
fun estimateHeightM(tags: Map<String, String>): Pair<Double, Boolean> {
    val rawHeight = tags["height"]
    if (rawHeight != null) {
        val parsed = parseMeters(rawHeight)
        if (parsed != null) return Pair(parsed, false)
    }

    val levels = tags["building:levels"] ?: tags["levels"]
    if (levels != null) {
        val n = try { levels.trim().toDouble() } catch (_: NumberFormatException) { null }
        if (n != null && n > 0) {
            return Pair(n * DEFAULT_LEVEL_HEIGHT_M, true)
        }
    }

    return Pair(DEFAULT_BUILDING_HEIGHT_M, true)
}

// ---------------------------------------------------------------------------
// GeoJSON loader
// ---------------------------------------------------------------------------

private val _json = Json { ignoreUnknownKeys = true }

/**
 * Parse a GeoJSON FeatureCollection [text] into a list of [Building]s.
 *
 * Handles Polygon and MultiPolygon geometries. Only the exterior ring (first
 * ring) of each polygon is used. GeoJSON coordinates are [lon, lat]; they are
 * swapped to (lat, lon) as required by [Building.ring].
 *
 * Rings with fewer than 3 distinct points are skipped.
 */
fun loadGeoJson(text: String): List<Building> {
    val root = _json.parseToJsonElement(text).jsonObject
    val features = root["features"]?.jsonArray ?: return emptyList()
    return featuresToBuildings(features)
}

private fun featuresToBuildings(features: JsonArray): List<Building> {
    val buildings = mutableListOf<Building>()

    for (featureElem in features) {
        val feature = featureElem as? JsonObject ?: continue
        val geometry = feature["geometry"] as? JsonObject ?: continue
        val gtype = (geometry["type"] as? JsonPrimitive)?.content ?: continue
        val coords = geometry["coordinates"] as? JsonArray ?: continue

        val props = feature["properties"] as? JsonObject
        val tags: Map<String, String> = props
            ?.entries
            ?.mapNotNull { (k, v) ->
                val prim = v as? JsonPrimitive ?: return@mapNotNull null
                k to prim.content
            }
            ?.toMap()
            ?: emptyMap()

        val (height, estimated) = estimateHeightM(tags)

        // OSM id: prefer properties["id"], then feature["id"]
        val osmId: String? = run {
            val fromProps = (props?.get("id") as? JsonPrimitive)?.content
            val fromFeature = (feature["id"] as? JsonPrimitive)?.content
            fromProps ?: fromFeature
        }

        // Collect exterior rings (first ring of each polygon)
        val exteriorRings: List<JsonArray> = when (gtype) {
            "Polygon" -> {
                val firstRing = coords.getOrNull(0) as? JsonArray
                if (firstRing != null) listOf(firstRing) else emptyList()
            }
            "MultiPolygon" -> {
                coords.mapNotNull { polyElem ->
                    val poly = polyElem as? JsonArray ?: return@mapNotNull null
                    poly.getOrNull(0) as? JsonArray
                }
            }
            else -> continue
        }

        for (ringCoords in exteriorRings) {
            val ring = ringCoords.mapNotNull { ptElem ->
                val pt = ptElem as? JsonArray ?: return@mapNotNull null
                if (pt.size < 2) return@mapNotNull null
                val lon = (pt[0] as? JsonPrimitive)?.content?.toDoubleOrNull() ?: return@mapNotNull null
                val lat = (pt[1] as? JsonPrimitive)?.content?.toDoubleOrNull() ?: return@mapNotNull null
                doubleArrayOf(lat, lon)   // swap: GeoJSON is [lon,lat]
            }
            if (ring.size >= 3) {
                buildings.add(
                    Building(
                        ring = ring,
                        heightM = height,
                        heightEstimated = estimated,
                        osmId = osmId,
                    )
                )
            }
        }
    }

    return buildings
}
