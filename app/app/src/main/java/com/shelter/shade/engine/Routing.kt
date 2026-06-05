package com.shelter.shade.engine

import java.util.PriorityQueue
import kotlin.math.tan

/** OSM 보행 그래프 기반 그늘 가중 라우팅. shade-engine/shade_engine/osm_routing.py 이식. */

data class RouteOption(
    val name: String,
    val alpha: Double,
    val coords: List<DoubleArray>, // [[lat,lon],...]
    val distanceM: Double,
    val sunFraction: Double,
) {
    val shadePercent: Double get() = ((1.0 - sunFraction) * 1000).toInt() / 10.0
}

class RouteNotFoundException(message: String) : RuntimeException(message)

private const val MAX_SHADOW_DISTANCE_CAP_M = 1500.0
private const val DEFAULT_MAX_SNAP_M = 200.0

fun planRoutesOsm(
    graph: OsmGraph,
    origin: DoubleArray, // [lat,lon]
    dest: DoubleArray,
    buildings: List<Building>,
    sunAzimuthDeg: Double,
    sunAltitudeDeg: Double,
    alphas: Map<String, Double>? = null,
    preferSun: Boolean = false,
    maxSnapM: Double = DEFAULT_MAX_SNAP_M,
): List<RouteOption> {
    val effectiveAlphas = alphas ?: linkedMapOf(
        "shortest" to 0.0,
        "balanced" to 3.0,
        (if (preferSun) "sunniest" else "shadiest") to 12.0,
    )

    if (graph.nodeCount() == 0) throw RouteNotFoundException("빈 보행 그래프")

    val lat0 = (origin[0] + dest[0]) / 2
    val lon0 = (origin[1] + dest[1]) / 2
    val proj = LocalProjection(lat0, lon0)
    val projected = projectBuildings(buildings, proj)
    val tallest = projected.maxOfOrNull { it.heightM } ?: 0.0
    val tanAlt = tan(Math.toRadians(maxOf(sunAltitudeDeg, 0.0)))
    val maxDist = if (tanAlt > 1e-6) minOf(MAX_SHADOW_DISTANCE_CAP_M, tallest / tanAlt) else MAX_SHADOW_DISTANCE_CAP_M
    val index = BuildingIndex(projected)

    val n = graph.nodeCount()
    val sunny = BooleanArray(n)
    val blocked = BooleanArray(n)
    for (i in 0 until n) {
        val xy = proj.toXy(graph.nodes[i][0], graph.nodes[i][1])
        val res = index.isPointShaded(xy, sunAzimuthDeg, sunAltitudeDeg, maxDistanceM = maxOf(maxDist, 20.0))
        sunny[i] = !res.shaded
        blocked[i] = res.reason == "inside_building"
    }

    val start = graph.nearestNode(origin[0], origin[1])
    val goal = graph.nearestNode(dest[0], dest[1])
    val oSnap = haversineM(origin[0], origin[1], graph.nodes[start][0], graph.nodes[start][1])
    val dSnap = haversineM(dest[0], dest[1], graph.nodes[goal][0], graph.nodes[goal][1])
    if (oSnap > maxSnapM || dSnap > maxSnapM) {
        throw RouteNotFoundException("보행망 범위 밖(스냅 ${oSnap.toInt()}m/${dSnap.toInt()}m)")
    }
    if (start == goal && haversineM(origin[0], origin[1], dest[0], dest[1]) > maxSnapM) {
        throw RouteNotFoundException("출발/도착이 같은 노드로 스냅됨")
    }
    blocked[start] = false
    blocked[goal] = false

    val avoid = DoubleArray(n) { i ->
        val a = if (preferSun) !sunny[i] else sunny[i]
        if (a) 1.0 else 0.0
    }

    val options = ArrayList<RouteOption>()
    for ((name, alpha) in effectiveAlphas) {
        val path = dijkstra(graph, start, goal, avoid, blocked, alpha)
            ?: throw RouteNotFoundException("출발-도착이 연결되지 않음")
        val coords = ArrayList<DoubleArray>(maxOf(path.size, 2))
        if (path.size <= 1) {
            // 출발·도착이 같은 노드로 스냅된 짧은 경로 → 양 끝점을 모두 보존
            coords.add(doubleArrayOf(origin[0], origin[1]))
            coords.add(doubleArrayOf(dest[0], dest[1]))
        } else {
            for (idx in path) coords.add(doubleArrayOf(graph.nodes[idx][0], graph.nodes[idx][1]))
            coords[0] = doubleArrayOf(origin[0], origin[1])
            coords[coords.size - 1] = doubleArrayOf(dest[0], dest[1])
        }
        var dist = 0.0
        for (k in 0 until coords.size - 1) {
            dist += haversineM(coords[k][0], coords[k][1], coords[k + 1][0], coords[k + 1][1])
        }
        val sunNodes = path.count { sunny[it] }
        val sunFrac = if (path.isEmpty()) 0.0 else sunNodes.toDouble() / path.size
        options.add(RouteOption(name, alpha, coords, dist, sunFrac))
    }
    return options
}

private fun dijkstra(
    graph: OsmGraph,
    start: Int,
    goal: Int,
    avoid: DoubleArray,
    blocked: BooleanArray,
    alpha: Double,
): List<Int>? {
    val dist = HashMap<Int, Double>()
    val prev = HashMap<Int, Int>()
    dist[start] = 0.0
    val pq = PriorityQueue<DoubleArray>(compareBy { it[0] }) // [cost, node]
    pq.add(doubleArrayOf(0.0, start.toDouble()))
    val visited = HashSet<Int>()

    while (pq.isNotEmpty()) {
        val top = pq.poll() ?: break
        val d = top[0]
        val u = top[1].toInt()
        if (u == goal) break
        if (u in visited) continue
        visited.add(u)
        for (edge in graph.adj[u].orEmpty()) {
            val v = edge.to
            if (blocked[v] && v != goal) continue
            val edgeAvoid = (avoid[u] + avoid[v]) / 2.0
            val nd = d + edge.lenM * (1.0 + alpha * edgeAvoid)
            if (nd < (dist[v] ?: Double.MAX_VALUE)) {
                dist[v] = nd
                prev[v] = u
                pq.add(doubleArrayOf(nd, v.toDouble()))
            }
        }
    }

    if (goal !in dist) return null
    val path = ArrayList<Int>()
    var cur = goal
    path.add(cur)
    while (cur != start) {
        cur = prev[cur] ?: return null
        path.add(cur)
    }
    path.reverse()
    return path
}
