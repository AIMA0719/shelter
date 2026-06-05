package com.shelter.shade.engine

import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.floor
import kotlin.math.hypot
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sin
import kotlin.math.tan

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

private const val EPS = 1e-9

// ---------------------------------------------------------------------------
// Data models
// ---------------------------------------------------------------------------

/**
 * Building footprint projected onto the local ENU (East/North) xy plane.
 *
 * [ringXy] elements are doubleArrayOf(x, y) where x = east metres, y = north metres.
 */
data class ProjectedBuilding(
    val ringXy: List<DoubleArray>,
    val heightM: Double,
    val heightEstimated: Boolean = false,
    val osmId: String? = null,
) {
    /** Returns [minX, minY, maxX, maxY]. */
    fun bbox(): DoubleArray {
        var minX = Double.MAX_VALUE
        var minY = Double.MAX_VALUE
        var maxX = -Double.MAX_VALUE
        var maxY = -Double.MAX_VALUE
        for (pt in ringXy) {
            if (pt[0] < minX) minX = pt[0]
            if (pt[1] < minY) minY = pt[1]
            if (pt[0] > maxX) maxX = pt[0]
            if (pt[1] > maxY) maxY = pt[1]
        }
        return doubleArrayOf(minX, minY, maxX, maxY)
    }
}

/**
 * Shade determination result for a single point.
 *
 * [reason] is one of: "sunny", "building", "inside_building", "sun_below".
 * [confidence] is in [0, 1]; reduced when building height is estimated and
 * close to the threshold.
 */
data class ShadeResult(
    val shaded: Boolean,
    val reason: String,
    val confidence: Double,
    val blockerId: String? = null,
    val blockerDistanceM: Double? = null,
)

// ---------------------------------------------------------------------------
// Geometry helpers (package-private — used by tests via same package)
// ---------------------------------------------------------------------------

/**
 * Point-in-polygon test using the ray casting algorithm.
 *
 * Points on the boundary are NOT considered inside (approximate).
 * Mirrors Python `_point_in_ring`.
 */
internal fun pointInRing(px: Double, py: Double, ring: List<DoubleArray>): Boolean {
    var inside = false
    val n = ring.size
    var j = n - 1
    for (i in 0 until n) {
        val xi = ring[i][0]; val yi = ring[i][1]
        val xj = ring[j][0]; val yj = ring[j][1]
        if ((yi > py) != (yj > py)) {
            val xCross = xi + (py - yi) / (yj - yi) * (xj - xi)
            if (px < xCross) inside = !inside
        }
        j = i
    }
    return inside
}

/**
 * Intersection distance between a ray (origin o, unit direction d) and a
 * line segment a→b.
 *
 * Returns the distance t ≥ 0 along the ray, or null if there is no
 * intersection (parallel or behind the origin or outside the segment).
 *
 * The derivation uses the 2-D cross-product formulation:
 *
 *   v1 = o - a
 *   v2 = b - a
 *   v3 = perp(d) = (-dy, dx)
 *
 *   t1 = cross(v2, v1) / dot(v2, v3)   [ray parameter]
 *   t2 = dot(v1, v3)  / dot(v2, v3)    [segment parameter ∈ [0,1]]
 *
 * This is identical to the Python `_ray_segment_distance` implementation.
 */
internal fun raySegmentDistance(
    ox: Double, oy: Double,
    dx: Double, dy: Double,
    ax: Double, ay: Double,
    bx: Double, by: Double,
): Double? {
    val v1x = ox - ax;  val v1y = oy - ay
    val v2x = bx - ax;  val v2y = by - ay
    val v3x = -dy;      val v3y = dx
    val denom = v2x * v3x + v2y * v3y
    if (abs(denom) < EPS) return null        // parallel
    val t1 = (v2x * v1y - v2y * v1x) / denom   // ray distance
    val t2 = (v1x * v3x + v1y * v3y) / denom   // segment parameter
    return if (t1 >= 0.0 && t2 >= 0.0 && t2 <= 1.0) t1 else null
}

/**
 * Minimum intersection distance between a ray and all edges of a polygon ring.
 *
 * Returns null when the ray does not intersect any edge.
 * Mirrors Python `_ray_ring_min_distance`.
 */
internal fun rayRingMinDistance(
    ox: Double, oy: Double,
    dx: Double, dy: Double,
    ring: List<DoubleArray>,
): Double? {
    var best: Double? = null
    val n = ring.size
    for (i in 0 until n) {
        val ax = ring[i][0];         val ay = ring[i][1]
        val bx = ring[(i + 1) % n][0]; val by = ring[(i + 1) % n][1]
        val d = raySegmentDistance(ox, oy, dx, dy, ax, ay, bx, by)
        if (d != null && (best == null || d < best)) best = d
    }
    return best
}

// ---------------------------------------------------------------------------
// Core shade determination
// ---------------------------------------------------------------------------

/**
 * Determine whether [pointXy] is shaded at the given solar position.
 *
 * [pointXy]       — [x, y] in local ENU metres (x = east, y = north).
 * [sunAzimuthDeg] — clockwise from north, degrees.
 * [sunAltitudeDeg]— elevation above horizon, degrees.
 * [buildings]     — projected building footprints to test against.
 * [maxDistanceM]  — ignore buildings further than this (metres).
 * [minAltitudeDeg]— sun altitude at or below this → "sun_below".
 *
 * Mirrors Python `is_point_shaded` exactly.
 */
fun isPointShaded(
    pointXy: DoubleArray,
    sunAzimuthDeg: Double,
    sunAltitudeDeg: Double,
    buildings: List<ProjectedBuilding>,
    maxDistanceM: Double = 1000.0,
    minAltitudeDeg: Double = 0.5,
): ShadeResult {
    if (sunAltitudeDeg <= minAltitudeDeg) {
        return ShadeResult(shaded = true, reason = "sun_below", confidence = 1.0)
    }

    val ox = pointXy[0]; val oy = pointXy[1]
    val az = Math.toRadians(sunAzimuthDeg)
    val dx = sin(az); val dy = cos(az)          // unit vector toward sun (east, north)
    val tanAlt = tan(Math.toRadians(sunAltitudeDeg))

    var nearestBlockerDist: Double? = null
    var nearestBlockerId: String? = null
    var confidence = 1.0

    for (b in buildings) {
        val bb = b.bbox()
        val minX = bb[0]; val minY = bb[1]; val maxX = bb[2]; val maxY = bb[3]
        // Fast bbox pre-filter: corridor distance lower-bound
        val ddx = max(minX - ox, max(0.0, ox - maxX))
        val ddy = max(minY - oy, max(0.0, oy - maxY))
        if (hypot(ddx, ddy) > maxDistanceM) continue

        if (pointInRing(ox, oy, b.ringXy)) {
            return ShadeResult(
                shaded = true,
                reason = "inside_building",
                confidence = if (!b.heightEstimated) 1.0 else 0.7,
                blockerId = b.osmId,
                blockerDistanceM = 0.0,
            )
        }

        val d = rayRingMinDistance(ox, oy, dx, dy, b.ringXy) ?: continue
        if (d > maxDistanceM) continue

        val required = d * tanAlt    // height needed to block sun at this distance
        if (b.heightM >= required) {
            if (nearestBlockerDist == null || d < nearestBlockerDist) {
                nearestBlockerDist = d
                nearestBlockerId = b.osmId
            }
            // Confidence reduction: estimated height AND close to threshold
            if (required > 0 && b.heightEstimated && b.heightM < required * 1.2) {
                confidence = min(confidence, 0.6)
            }
        }
    }

    return if (nearestBlockerDist != null) {
        ShadeResult(
            shaded = true,
            reason = "building",
            confidence = confidence,
            blockerId = nearestBlockerId,
            blockerDistanceM = nearestBlockerDist,
        )
    } else {
        ShadeResult(shaded = false, reason = "sunny", confidence = confidence)
    }
}

// ---------------------------------------------------------------------------
// Spatial index
// ---------------------------------------------------------------------------

/**
 * Uniform-grid spatial index over projected buildings.
 *
 * Each building is bucketed into all grid cells its bounding box overlaps.
 * [candidates] returns a deduplicated list of buildings in all cells that
 * could contain buildings within [radius] of (x, y).
 *
 * Mirrors Python `BuildingIndex`.
 */
class BuildingIndex(buildings: List<ProjectedBuilding>, private val cellSizeM: Double = 64.0) {

    // grid cell → list of buildings whose bbox overlaps that cell
    private val grid: HashMap<Long, MutableList<ProjectedBuilding>> = HashMap()

    init {
        for (b in buildings) {
            val bb = b.bbox()
            val minX = bb[0]; val minY = bb[1]; val maxX = bb[2]; val maxY = bb[3]
            for (cx in cell(minX)..cell(maxX)) {
                for (cy in cell(minY)..cell(maxY)) {
                    grid.getOrPut(packCell(cx, cy)) { mutableListOf() }.add(b)
                }
            }
        }
    }

    private fun cell(v: Double): Int = floor(v / cellSizeM).toInt()

    /** Pack two ints into a Long for use as a HashMap key. */
    private fun packCell(cx: Int, cy: Int): Long =
        (cx.toLong() and 0xFFFF_FFFFL) or (cy.toLong() shl 32)

    /**
     * Return all unique candidate buildings within cells that could contain
     * buildings within [radius] metres of ([x], [y]).
     *
     * Uses object identity (System.identityHashCode) to deduplicate, mirroring
     * Python's `id(b)` dict key.
     */
    fun candidates(x: Double, y: Double, radius: Double): List<ProjectedBuilding> {
        val seen = LinkedHashMap<Int, ProjectedBuilding>()
        for (cx in cell(x - radius)..cell(x + radius)) {
            for (cy in cell(y - radius)..cell(y + radius)) {
                val bucket = grid[packCell(cx, cy)] ?: continue
                for (b in bucket) {
                    seen[System.identityHashCode(b)] = b
                }
            }
        }
        return seen.values.toList()
    }

    /**
     * Shade determination using the spatial index.
     *
     * Mirrors Python `BuildingIndex.is_point_shaded`.
     */
    fun isPointShaded(
        pointXy: DoubleArray,
        sunAzimuthDeg: Double,
        sunAltitudeDeg: Double,
        maxDistanceM: Double = 1000.0,
        minAltitudeDeg: Double = 0.5,
    ): ShadeResult {
        if (sunAltitudeDeg <= minAltitudeDeg) {
            return ShadeResult(shaded = true, reason = "sun_below", confidence = 1.0)
        }
        val cands = candidates(pointXy[0], pointXy[1], maxDistanceM)
        return isPointShaded(pointXy, sunAzimuthDeg, sunAltitudeDeg, cands, maxDistanceM, minAltitudeDeg)
    }
}
