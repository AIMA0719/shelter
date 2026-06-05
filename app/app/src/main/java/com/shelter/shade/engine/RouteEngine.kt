package com.shelter.shade.engine

import kotlin.math.tan

/** 경로 그늘 판정 엔진(온디바이스). shade-engine/shade_engine/engine.py 이식. */

data class SamplePoint(
    val lat: Double,
    val lon: Double,
    val distanceM: Double,
    val sunAzimuthDeg: Double,
    val sunAltitudeDeg: Double,
    val result: ShadeResult,
)

data class RouteShade(
    val samples: List<SamplePoint>,
    val totalDistanceM: Double,
    val shadedCount: Int,
    val sunnyCount: Int,
) {
    val totalCount: Int get() = samples.size
    val shadeFraction: Double
        get() {
            val considered = shadedCount + sunnyCount
            return if (considered == 0) 1.0 else shadedCount.toDouble() / considered
        }
    val shadePercent: Double get() = (shadeFraction * 1000).toInt() / 10.0
    val meanConfidence: Double
        get() = if (samples.isEmpty()) 0.0 else samples.sumOf { it.result.confidence } / samples.size
}

const val DEFAULT_SPACING_M = 10.0
const val DEFAULT_WALK_SPEED_MPS = 1.3
const val DEFAULT_BIKE_SPEED_MPS = 4.2
private const val MAX_SHADOW_DISTANCE_CAP_M = 1500.0

/** coords: [[lat,lon],...] → [[lat,lon,cumulativeDistanceM],...] (engine.sample_polyline 이식). */
fun samplePolyline(coords: List<DoubleArray>, spacingM: Double = DEFAULT_SPACING_M): List<DoubleArray> {
    if (coords.isEmpty()) return emptyList()
    if (coords.size == 1) return listOf(doubleArrayOf(coords[0][0], coords[0][1], 0.0))
    require(spacingM > 0) { "spacingM must be > 0" }

    val eps = 1e-6
    val out = ArrayList<DoubleArray>()
    out.add(doubleArrayOf(coords[0][0], coords[0][1], 0.0))
    var cumulative = 0.0
    var nextTarget = spacingM

    for (i in 0 until coords.size - 1) {
        val la1 = coords[i][0]; val lo1 = coords[i][1]
        val la2 = coords[i + 1][0]; val lo2 = coords[i + 1][1]
        val segLen = haversineM(la1, lo1, la2, lo2)
        if (segLen < 1e-9) continue
        val segEnd = cumulative + segLen
        while (nextTarget <= segEnd + eps) {
            val frac = ((nextTarget - cumulative) / segLen).coerceIn(0.0, 1.0)
            out.add(doubleArrayOf(la1 + (la2 - la1) * frac, lo1 + (lo2 - lo1) * frac, nextTarget))
            nextTarget += spacingM
        }
        cumulative = segEnd
    }
    if (out.last()[2] < cumulative - eps) {
        val last = coords.last()
        out.add(doubleArrayOf(last[0], last[1], cumulative))
    }
    return out
}

internal fun projectBuildings(buildings: List<Building>, proj: LocalProjection): List<ProjectedBuilding> =
    buildings.mapNotNull { b ->
        val ringXy = b.ring.map { proj.toXy(it[0], it[1]) }
        if (ringXy.size >= 3) {
            ProjectedBuilding(ringXy = ringXy, heightM = b.heightM, heightEstimated = b.heightEstimated, osmId = b.osmId)
        } else {
            null
        }
    }

fun computeRouteShade(
    coords: List<DoubleArray>,
    departEpochMillis: Long,
    buildings: List<Building>,
    spacingM: Double = DEFAULT_SPACING_M,
    walkSpeedMps: Double = DEFAULT_WALK_SPEED_MPS,
    movingSun: Boolean = true,
    minAltitudeDeg: Double = 0.5,
): RouteShade {
    val samplesGeo = samplePolyline(coords, spacingM)
    if (samplesGeo.isEmpty()) return RouteShade(emptyList(), 0.0, 0, 0)

    val lat0 = samplesGeo.sumOf { it[0] } / samplesGeo.size
    val lon0 = samplesGeo.sumOf { it[1] } / samplesGeo.size
    val proj = LocalProjection(lat0, lon0)
    val projected = projectBuildings(buildings, proj)
    val tallest = projected.maxOfOrNull { it.heightM } ?: 0.0
    val index = BuildingIndex(projected)

    val out = ArrayList<SamplePoint>(samplesGeo.size)
    var shaded = 0
    var sunny = 0

    for (s in samplesGeo) {
        val lat = s[0]; val lon = s[1]; val dist = s[2]
        val arrival = if (movingSun) departEpochMillis + ((dist / walkSpeedMps) * 1000.0).toLong() else departEpochMillis
        val sun = solarPosition(lat, lon, arrival)
        val xy = proj.toXy(lat, lon)
        val result = if (sun.altitudeDeg <= minAltitudeDeg) {
            index.isPointShaded(xy, sun.azimuthDeg, sun.altitudeDeg, minAltitudeDeg = minAltitudeDeg)
        } else {
            val tanAlt = tan(Math.toRadians(sun.altitudeDeg))
            val maxDist = if (tanAlt > 1e-6) minOf(MAX_SHADOW_DISTANCE_CAP_M, tallest / tanAlt) else MAX_SHADOW_DISTANCE_CAP_M
            index.isPointShaded(xy, sun.azimuthDeg, sun.altitudeDeg, maxDistanceM = maxOf(maxDist, spacingM), minAltitudeDeg = minAltitudeDeg)
        }
        if (result.reason == "sunny") sunny++ else shaded++
        out.add(SamplePoint(lat, lon, dist, sun.azimuthDeg, sun.altitudeDeg, result))
    }
    return RouteShade(out, samplesGeo.last()[2], shaded, sunny)
}
