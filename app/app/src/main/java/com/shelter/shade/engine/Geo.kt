package com.shelter.shade.engine

import kotlin.math.*

// WGS84: metres per degree of latitude (constant)
private const val M_PER_DEG_LAT = 111_320.0

// Metres per degree of longitude at the equator (same value, scaled by cos(lat0))
private const val M_PER_DEG_LON_EQUATOR = 111_320.0

/** Mean Earth radius in metres. */
const val EARTH_RADIUS_M = 6_371_000.0

/**
 * Flat-Earth ENU (East / North) projection centred on [lat0], [lon0].
 *
 * x = east (metres, +), y = north (metres, +).
 * Accurate for city-block / walking-path scale areas only.
 *
 * Mirrors Python `geo.LocalProjection`.
 */
class LocalProjection(val lat0: Double, val lon0: Double) {

    /** Metres per degree of longitude at the reference latitude. */
    private val mPerDegLon: Double = M_PER_DEG_LON_EQUATOR * cos(Math.toRadians(lat0))

    /**
     * Convert geographic coordinates to local ENU metres.
     *
     * @return `[x, y]` where x = east metres, y = north metres.
     */
    fun toXy(lat: Double, lon: Double): DoubleArray {
        val x = (lon - lon0) * mPerDegLon
        val y = (lat - lat0) * M_PER_DEG_LAT
        return doubleArrayOf(x, y)
    }

    /**
     * Inverse of [toXy] — convert local ENU metres back to geographic coordinates.
     *
     * @return `[lat, lon]`.
     */
    fun toLatLon(x: Double, y: Double): DoubleArray {
        val lon = lon0 + x / mPerDegLon
        val lat = lat0 + y / M_PER_DEG_LAT
        return doubleArrayOf(lat, lon)
    }
}

/**
 * Great-circle distance between two geographic points using the Haversine formula.
 *
 * @return Distance in metres.
 */
fun haversineM(lat1: Double, lon1: Double, lat2: Double, lon2: Double): Double {
    val p1 = Math.toRadians(lat1)
    val p2 = Math.toRadians(lat2)
    val dPhi = Math.toRadians(lat2 - lat1)
    val dLambda = Math.toRadians(lon2 - lon1)
    val a = sin(dPhi / 2).pow(2) + cos(p1) * cos(p2) * sin(dLambda / 2).pow(2)
    return 2.0 * EARTH_RADIUS_M * asin(min(1.0, sqrt(a)))
}

/**
 * Forward azimuth (bearing) from point 1 to point 2.
 *
 * @return Bearing in degrees, north = 0, clockwise, range [0, 360).
 */
fun bearingDeg(lat1: Double, lon1: Double, lat2: Double, lon2: Double): Double {
    val p1 = Math.toRadians(lat1)
    val p2 = Math.toRadians(lat2)
    val dl = Math.toRadians(lon2 - lon1)
    val y = sin(dl) * cos(p2)
    val x = cos(p1) * sin(p2) - sin(p1) * cos(p2) * cos(dl)
    return (Math.toDegrees(atan2(y, x)) + 360.0) % 360.0
}
