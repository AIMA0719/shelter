package com.shelter.shade.engine

import android.content.Context
import com.shelter.shade.data.DepartureCandidateOut
import com.shelter.shade.data.DepartureSuggestResponse
import com.shelter.shade.data.LatLng
import com.shelter.shade.data.RouteOptionOut
import com.shelter.shade.data.RoutesResponse
import com.shelter.shade.data.SegmentOut
import com.shelter.shade.data.ShadeResponse
import com.shelter.shade.data.WeatherBadge
import java.time.Instant
import java.time.ZoneOffset

/**
 * 백엔드 없이 기기에서 직접 그늘/경로를 계산하는 엔진 facade.
 * 강남 권역 건물(GIS건물통합정보 변환)과 OSM 보행망을 앱 에셋에서 로드한다.
 */
class LocalShadeEngine private constructor(
    private val buildings: List<Building>,
    private val walkGraph: OsmGraph?,
) {
    val buildingCount: Int get() = buildings.size
    val walkNodeCount: Int get() = walkGraph?.nodeCount() ?: 0

    /** 이 엔진(강남 권역 에셋)이 해당 좌표를 덮는지 — 서버 실패 시 폴백 가능 여부 판단용. */
    fun covers(ll: LatLng): Boolean {
        val bb = bbox ?: return false
        return ll.lat in bb[0]..bb[2] && ll.lon in bb[1]..bb[3]
    }

    private val bbox: DoubleArray? = run {
        if (buildings.isEmpty()) {
            null
        } else {
            var mnLat = Double.MAX_VALUE; var mnLon = Double.MAX_VALUE
            var mxLat = -Double.MAX_VALUE; var mxLon = -Double.MAX_VALUE
            for (b in buildings) {
                val bb = b.bbox()
                if (bb[0] < mnLat) mnLat = bb[0]; if (bb[1] < mnLon) mnLon = bb[1]
                if (bb[2] > mxLat) mxLat = bb[2]; if (bb[3] > mxLon) mxLon = bb[3]
            }
            doubleArrayOf(mnLat, mnLon, mxLat, mxLon)
        }
    }

    /** origin→dest 단일 경로의 그늘 색칠(직선 보간 경로). */
    fun computeShade(
        origin: LatLng, dest: LatLng, departEpochMillis: Long, departIso: String, mode: String,
    ): ShadeResponse {
        val coords = straightLine(origin, dest)
        val nearby = buildingsNear(coords)
        val rs = computeRouteShade(
            coords, departEpochMillis, nearby, spacingM = 10.0, walkSpeedMps = speedFor(mode),
        )
        return ShadeResponse(
            shadePercent = rs.shadePercent,
            totalDistanceM = round1(rs.totalDistanceM),
            sampleCount = rs.totalCount,
            meanConfidence = round3(rs.meanConfidence),
            departTime = departIso,
            mode = mode,
            provider = "local",
            buildingCount = nearby.size,
            cached = false,
            segments = segmentsOf(rs),
        )
    }

    /** 최단/균형/그늘(또는 햇빛) 경로 비교 + 쾌적도 + 날씨. */
    fun planRoutes(
        origin: LatLng, dest: LatLng, departEpochMillis: Long, departIso: String, mode: String, prefer: String,
    ): RoutesResponse {
        val zdt = Instant.ofEpochMilli(departEpochMillis).atZone(KST)
        val weather = Weather.badge(zdt.monthValue, zdt.hour)

        val originArr = doubleArrayOf(origin.lat, origin.lon)
        val destArr = doubleArrayOf(dest.lat, dest.lon)
        val nearby = buildingsNear(listOf(originArr, destArr))

        // 도보 + 보행망 있으면 OSM 라우팅, 아니면 직선 단일 경로.
        var routing = "straight"
        var rawOptions: List<RouteOption>
        val sun = solarPosition(origin.lat, origin.lon, departEpochMillis)
        if (mode == "walk" && walkGraph != null && walkGraph.nodeCount() > 0) {
            rawOptions = try {
                routing = "osm"
                planRoutesOsm(walkGraph, originArr, destArr, nearby, sun.azimuthDeg, sun.altitudeDeg, preferSun = prefer == "sun")
            } catch (e: RouteNotFoundException) {
                routing = "straight"
                straightOptions(origin, dest, prefer)
            }
        } else {
            rawOptions = straightOptions(origin, dest, prefer)
        }

        val options = rawOptions.map { opt ->
            val rs = computeRouteShade(opt.coords, departEpochMillis, nearby, spacingM = 10.0, walkSpeedMps = speedFor(mode))
            RouteOptionOut(
                name = opt.name,
                distanceM = round1(opt.distanceM),
                shadePercent = rs.shadePercent,
                comfort = Comfort.score(rs.shadeFraction, weather.tempC, weather.uvIndex),
                coords = opt.coords.map { LatLng(it[0], it[1]) },
                segments = segmentsOf(rs),
            )
        }
        return RoutesResponse(
            departTime = departIso,
            mode = mode,
            prefer = prefer,
            routing = routing,
            buildingCount = nearby.size,
            cached = false,
            weather = WeatherBadge(
                tempC = weather.tempC, uvIndex = weather.uvIndex, heatAdvisory = weather.heatAdvisory, source = weather.source,
            ),
            options = options,
        )
    }

    /** 후보 출발 시각별 그늘 평가 + 최적 시각 추천. */
    fun suggestDeparture(
        origin: LatLng, dest: LatLng, baseDateEpochMillis: Long, mode: String, prefer: String,
        hours: List<Int> = listOf(8, 10, 12, 14, 16, 18),
    ): DepartureSuggestResponse {
        val baseDate = Instant.ofEpochMilli(baseDateEpochMillis).atZone(KST).toLocalDate()
        val coords = straightLine(origin, dest)
        val nearby = buildingsNear(coords)
        val cands = hours.map { h ->
            val odt = baseDate.atTime(h, 0).atOffset(KST)
            val epoch = odt.toInstant().toEpochMilli()
            val rs = computeRouteShade(coords, epoch, nearby, spacingM = 10.0, walkSpeedMps = speedFor(mode))
            DepartureCandidateOut(departTime = odt.toString(), shadePercent = rs.shadePercent)
        }
        val best = if (prefer == "sun") cands.minByOrNull { it.shadePercent } else cands.maxByOrNull { it.shadePercent }
        return DepartureSuggestResponse(best = best ?: cands.first(), prefer = prefer, candidates = cands)
    }

    // --- helpers ---

    private fun straightOptions(origin: LatLng, dest: LatLng, prefer: String): List<RouteOption> {
        val coords = straightLine(origin, dest)
        var dist = 0.0
        for (k in 0 until coords.size - 1) dist += haversineM(coords[k][0], coords[k][1], coords[k + 1][0], coords[k + 1][1])
        val name = if (prefer == "sun") "sunniest" else "shadiest"
        // 그래프가 없으면 대안 경로를 만들 수 없으므로 동일 경로 1개만 제공.
        return listOf(RouteOption("shortest", 0.0, coords, dist, 0.0), RouteOption(name, 12.0, coords, dist, 0.0))
    }

    private fun straightLine(origin: LatLng, dest: LatLng, stepM: Double = 25.0): List<DoubleArray> {
        val d = haversineM(origin.lat, origin.lon, dest.lat, dest.lon)
        val n = maxOf(1, (d / stepM).toInt())
        return (0..n).map { i ->
            doubleArrayOf(origin.lat + (dest.lat - origin.lat) * i / n, origin.lon + (dest.lon - origin.lon) * i / n)
        }
    }

    private fun buildingsNear(coords: List<DoubleArray>): List<Building> {
        if (buildings.isEmpty() || coords.isEmpty()) return buildings
        var mnLat = Double.MAX_VALUE; var mnLon = Double.MAX_VALUE
        var mxLat = -Double.MAX_VALUE; var mxLon = -Double.MAX_VALUE
        for (c in coords) {
            if (c[0] < mnLat) mnLat = c[0]; if (c[1] < mnLon) mnLon = c[1]
            if (c[0] > mxLat) mxLat = c[0]; if (c[1] > mxLon) mxLon = c[1]
        }
        // 그림자 탐색 최대 반경(1.5km)과 일치하는 패딩 — 저각도 태양의 먼 고층 그림자 누락 방지.
        val padM = 1500.0
        val dLat = padM / 111_320.0
        val dLon = padM / (111_320.0 * Math.cos(Math.toRadians((mnLat + mxLat) / 2)))
        mnLat -= dLat; mxLat += dLat; mnLon -= dLon; mxLon += dLon
        return buildings.filter { b ->
            val bb = b.bbox()
            !(bb[2] < mnLat || bb[0] > mxLat || bb[3] < mnLon || bb[1] > mxLon)
        }
    }

    private fun speedFor(mode: String): Double = if (mode == "bike") DEFAULT_BIKE_SPEED_MPS else DEFAULT_WALK_SPEED_MPS

    private fun segmentsOf(rs: RouteShade): List<SegmentOut> =
        rs.samples.zipWithNext { s, next ->
            SegmentOut(
                a = LatLng(s.lat, s.lon),
                b = LatLng(next.lat, next.lon),
                shaded = s.result.shaded,
                reason = s.result.reason,
                confidence = round3(s.result.confidence),
            )
        }

    companion object {
        private val KST = ZoneOffset.ofHours(9)

        @Volatile private var instance: LocalShadeEngine? = null

        fun get(context: Context): LocalShadeEngine =
            instance ?: synchronized(this) { instance ?: load(context.applicationContext).also { instance = it } }

        private fun load(ctx: Context): LocalShadeEngine {
            val b = readAsset(ctx, "seoul_gangnam_buildings.geojson")?.let { loadGeoJson(it) } ?: emptyList()
            val g = readAsset(ctx, "seoul_gangnam_walk_network.geojson")
                ?.takeIf { it.isNotBlank() }?.let { OsmGraph.fromGeoJson(it) }
            return LocalShadeEngine(b, g)
        }

        private fun readAsset(ctx: Context, name: String): String? =
            try {
                ctx.assets.open(name).bufferedReader().use { it.readText() }
            } catch (e: Exception) {
                null
            }
    }
}

private fun round1(v: Double): Double = Math.round(v * 10.0) / 10.0
private fun round3(v: Double): Double = Math.round(v * 1000.0) / 1000.0
