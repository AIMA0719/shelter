package com.shelter.shade.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.unit.dp
import com.shelter.shade.data.SegmentOut
import com.shelter.shade.ui.theme.ShadeGreen
import com.shelter.shade.ui.theme.SunOrange
import kotlin.math.cos

/**
 * 지도 SDK 결정 전(MVP)용 자립형 경로 시각화.
 * 그늘 구간은 초록, 햇빛 구간은 주황으로 폴리라인을 그린다. 외부 지도 SDK 불필요.
 * 지도 SDK 확정 후 이 컴포저블을 실제 지도 오버레이로 교체한다.
 */
@Composable
fun RouteCanvas(
    segments: List<SegmentOut>,
    modifier: Modifier = Modifier,
) {
    if (segments.isEmpty()) return

    val lats = segments.flatMap { listOf(it.a.lat, it.b.lat) }
    val lons = segments.flatMap { listOf(it.a.lon, it.b.lon) }
    val minLat = lats.min()
    val maxLat = lats.max()
    val minLon = lons.min()
    val maxLon = lons.max()
    val meanLatRad = Math.toRadians((minLat + maxLat) / 2.0)
    val lonScale = cos(meanLatRad)

    Canvas(modifier = modifier.fillMaxWidth().height(280.dp)) {
        val pad = 24f
        val w = size.width - pad * 2
        val h = size.height - pad * 2
        val spanX = ((maxLon - minLon) * lonScale).coerceAtLeast(1e-9)
        val spanY = (maxLat - minLat).coerceAtLeast(1e-9)
        // 가로/세로 비율 유지(등방 스케일)
        val scale = minOf(w / spanX, h / spanY)
        val drawW = spanX * scale
        val drawH = spanY * scale
        val offX = pad + (w - drawW) / 2
        val offY = pad + (h - drawH) / 2

        fun project(lat: Double, lon: Double): Offset {
            val x = ((lon - minLon) * lonScale) * scale + offX
            // 위도가 클수록 위쪽(y 작게)
            val y = (maxLat - lat) * scale + offY
            return Offset(x.toFloat(), y.toFloat())
        }

        segments.forEach { seg ->
            drawLine(
                color = if (seg.shaded) ShadeGreen else SunOrange,
                start = project(seg.a.lat, seg.a.lon),
                end = project(seg.b.lat, seg.b.lon),
                strokeWidth = 14f,
                cap = StrokeCap.Round,
            )
        }
    }
}
