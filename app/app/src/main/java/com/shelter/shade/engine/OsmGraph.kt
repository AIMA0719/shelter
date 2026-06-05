package com.shelter.shade.engine

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlin.math.floor

/** OSM 보행 그래프. shade-engine/shade_engine/osm_graph.py 이식.
 *  nodes[i] = [lat, lon]; adj[i] = 인접 엣지 목록(to 인덱스, 거리m). */
class Edge(val to: Int, val lenM: Double)

private const val NEAREST_CELL_DEG = 0.002
private const val DEG_TO_M_LOWER = 88_000.0

class OsmGraph(
    val nodes: List<DoubleArray>,
    val adj: Map<Int, List<Edge>>,
) {
    private var index: HashMap<Long, MutableList<Int>>? = null

    fun nodeCount(): Int = nodes.size
    fun edgeCount(): Int = adj.values.sumOf { it.size } / 2

    private fun cellKey(cx: Int, cy: Int): Long = (cx.toLong() shl 32) or (cy.toLong() and 0xFFFF_FFFFL)

    private fun ensureIndex() {
        if (index != null) return
        val g = HashMap<Long, MutableList<Int>>()
        for (i in nodes.indices) {
            val cx = floor(nodes[i][0] / NEAREST_CELL_DEG).toInt()
            val cy = floor(nodes[i][1] / NEAREST_CELL_DEG).toInt()
            g.getOrPut(cellKey(cx, cy)) { ArrayList() }.add(i)
        }
        index = g
    }

    fun nearestNode(lat: Double, lon: Double): Int {
        require(nodes.isNotEmpty()) { "빈 그래프" }
        ensureIndex()
        val idx = index!!
        val cellM = NEAREST_CELL_DEG * DEG_TO_M_LOWER
        val cx = floor(lat / NEAREST_CELL_DEG).toInt()
        val cy = floor(lon / NEAREST_CELL_DEG).toInt()
        var bestI = -1
        var bestD = Double.MAX_VALUE
        var r = 0
        val maxR = 64
        while (r <= maxR) {
            for (cellPair in ringCells(cx, cy, r)) {
                idx[cellKey(cellPair[0], cellPair[1])]?.let { ids ->
                    for (ni in ids) {
                        val d = haversineM(lat, lon, nodes[ni][0], nodes[ni][1])
                        if (d < bestD) { bestD = d; bestI = ni }
                    }
                }
            }
            if (bestI >= 0 && bestD <= r * cellM) return bestI
            r++
        }
        // 상한까지 확정 못하면 전수 스캔(정확성 보장)
        for (ni in nodes.indices) {
            val d = haversineM(lat, lon, nodes[ni][0], nodes[ni][1])
            if (d < bestD) { bestD = d; bestI = ni }
        }
        return bestI
    }

    companion object {
        private val json = Json { ignoreUnknownKeys = true }

        /** LineString/MultiLineString GeoJSON([lon,lat]) → 보행 그래프. 좌표 공유로 위상 복원. */
        fun fromGeoJson(text: String): OsmGraph {
            val root = json.parseToJsonElement(text).jsonObject
            val features = root["features"]?.jsonArray ?: return OsmGraph(emptyList(), emptyMap())

            val coordId = HashMap<String, Int>()
            val nodes = ArrayList<DoubleArray>()
            val adj = HashMap<Int, MutableList<Edge>>()

            fun nodeId(lat: Double, lon: Double): Int {
                val key = "%.7f,%.7f".format(lat, lon)
                return coordId.getOrPut(key) { nodes.add(doubleArrayOf(lat, lon)); nodes.size - 1 }
            }
            fun addEdge(a: Int, b: Int) {
                if (a == b) return
                val d = haversineM(nodes[a][0], nodes[a][1], nodes[b][0], nodes[b][1])
                adj.getOrPut(a) { ArrayList() }.add(Edge(b, d))
                adj.getOrPut(b) { ArrayList() }.add(Edge(a, d))
            }

            for (featElem in features) {
                val geom = (featElem as? JsonObject)?.get("geometry") as? JsonObject ?: continue
                val gtype = (geom["type"] as? JsonPrimitive)?.content ?: continue
                val coords = geom["coordinates"] as? JsonArray ?: continue
                val lines: List<JsonArray> = when (gtype) {
                    "LineString" -> listOf(coords)
                    "MultiLineString" -> coords.mapNotNull { it as? JsonArray }
                    else -> continue
                }
                for (line in lines) {
                    val ids = line.mapNotNull { ptElem ->
                        val pt = ptElem as? JsonArray ?: return@mapNotNull null
                        if (pt.size < 2) return@mapNotNull null
                        val lon = (pt[0] as? JsonPrimitive)?.content?.toDoubleOrNull() ?: return@mapNotNull null
                        val lat = (pt[1] as? JsonPrimitive)?.content?.toDoubleOrNull() ?: return@mapNotNull null
                        nodeId(lat, lon)
                    }
                    for (k in 0 until ids.size - 1) addEdge(ids[k], ids[k + 1])
                }
            }
            return OsmGraph(nodes, adj)
        }
    }
}

/** 중심(cx,cy)에서 체비셰프 거리 r 인 셀들(경계 링). 각 원소 [ix,iy]. */
internal fun ringCells(cx: Int, cy: Int, r: Int): List<IntArray> {
    if (r == 0) return listOf(intArrayOf(cx, cy))
    val out = ArrayList<IntArray>()
    for (ix in (cx - r)..(cx + r)) {
        out.add(intArrayOf(ix, cy - r))
        out.add(intArrayOf(ix, cy + r))
    }
    for (iy in (cy - r + 1)..(cy + r - 1)) {
        out.add(intArrayOf(cx - r, iy))
        out.add(intArrayOf(cx + r, iy))
    }
    return out
}
