@file:OptIn(ExperimentalNaverMapApi::class)

package com.shelter.shade.ui

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.naver.maps.geometry.LatLng as NaverLatLng
import com.naver.maps.map.CameraPosition
import com.naver.maps.map.compose.ExperimentalNaverMapApi
import com.naver.maps.map.compose.NaverMap
import com.naver.maps.map.compose.PolylineOverlay
import com.naver.maps.map.compose.rememberCameraPositionState
import com.shelter.shade.data.SegmentOut
import com.shelter.shade.ui.theme.ShadeGreen
import com.shelter.shade.ui.theme.SunOrange

/**
 * 네이버 지도 위에 경로를 그늘/햇빛으로 색칠해 표시한다.
 * 지도 SDK 는 "표시"만 담당하고, 그늘/경로 판정은 백엔드 엔진 결과(segments)를 그대로 그린다.
 *
 * NCP 키는 AndroidManifest 의 meta-data(com.naver.maps.map.NCP_KEY_ID)로 주입된다
 * (build.gradle 이 local.properties 의 NCP_KEY_ID 를 읽음).
 */
@Composable
fun NaverRouteMap(segments: List<SegmentOut>, modifier: Modifier = Modifier) {
    if (segments.isEmpty()) return

    val center = remember(segments) {
        val lat = segments.flatMap { listOf(it.a.lat, it.b.lat) }.average()
        val lon = segments.flatMap { listOf(it.a.lon, it.b.lon) }.average()
        NaverLatLng(lat, lon)
    }
    val cameraPositionState = rememberCameraPositionState {
        position = CameraPosition(center, 16.0)
    }

    NaverMap(
        modifier = modifier.fillMaxWidth().height(280.dp),
        cameraPositionState = cameraPositionState,
    ) {
        segments.forEach { seg ->
            PolylineOverlay(
                coords = listOf(
                    NaverLatLng(seg.a.lat, seg.a.lon),
                    NaverLatLng(seg.b.lat, seg.b.lon),
                ),
                color = if (seg.shaded) ShadeGreen else SunOrange,
                width = 6.dp,
            )
        }
    }
}
