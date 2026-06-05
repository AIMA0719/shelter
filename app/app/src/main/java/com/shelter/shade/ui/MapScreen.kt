@file:OptIn(ExperimentalNaverMapApi::class)

package com.shelter.shade.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Slider
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.SwapVert
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.naver.maps.geometry.LatLngBounds
import com.naver.maps.map.CameraPosition
import com.naver.maps.map.CameraUpdate
import com.naver.maps.map.compose.ExperimentalNaverMapApi
import com.naver.maps.map.compose.MapUiSettings
import com.naver.maps.map.compose.Marker
import com.naver.maps.map.compose.NaverMap
import com.naver.maps.map.compose.PolylineOverlay
import com.naver.maps.map.compose.rememberCameraPositionState
import com.naver.maps.map.compose.rememberMarkerState
import androidx.compose.runtime.LaunchedEffect
import com.naver.maps.geometry.LatLng as NaverLatLng
import com.shelter.shade.data.PlaceResult
import com.shelter.shade.data.RouteOptionOut
import com.shelter.shade.data.WeatherBadge
import com.shelter.shade.ui.theme.ShadeGreen
import com.shelter.shade.ui.theme.SunOrange

private val OriginBlue = Color(0xFF1E88E5)
private val DestRed = Color(0xFFE53935)

@Composable
fun MapScreen(viewModel: ShadeViewModel) {
    val state by viewModel.state.collectAsState()
    val camera = rememberCameraPositionState {
        position = CameraPosition(NaverLatLng(37.4979, 127.0276), 15.0)
    }

    val success = state.routes as? RoutesUiResult.Success
    val segments = success?.response?.options?.getOrNull(state.selectedOption)?.segments.orEmpty()

    // 지점이 정해지면 카메라 이동/맞춤
    LaunchedEffect(state.origin, state.dest) {
        val o = state.origin
        val d = state.dest
        runCatching {
            if (o != null && d != null) {
                val bounds = LatLngBounds.Builder()
                    .include(NaverLatLng(o.lat, o.lon)).include(NaverLatLng(d.lat, d.lon)).build()
                camera.animate(CameraUpdate.fitBounds(bounds, 250))
            } else if (o != null) {
                camera.animate(CameraUpdate.scrollTo(NaverLatLng(o.lat, o.lon)))
            } else if (d != null) {
                camera.animate(CameraUpdate.scrollTo(NaverLatLng(d.lat, d.lon)))
            }
        }
    }

    Box(Modifier.fillMaxSize()) {
        NaverMap(
            modifier = Modifier.fillMaxSize(),
            cameraPositionState = camera,
            uiSettings = MapUiSettings(isZoomControlEnabled = false, isScaleBarEnabled = true),
            onMapClick = { _, latLng -> viewModel.onMapTap(latLng.latitude, latLng.longitude) },
        ) {
            segments.forEach { seg ->
                PolylineOverlay(
                    coords = listOf(NaverLatLng(seg.a.lat, seg.a.lon), NaverLatLng(seg.b.lat, seg.b.lon)),
                    color = if (seg.shaded) ShadeGreen else SunOrange,
                    width = 7.dp,
                )
            }
            state.origin?.let { o ->
                Marker(
                    state = rememberMarkerState(key = "o-${o.lat}-${o.lon}", position = NaverLatLng(o.lat, o.lon)),
                    captionText = "출발",
                    iconTintColor = OriginBlue,
                )
            }
            state.dest?.let { d ->
                Marker(
                    state = rememberMarkerState(key = "d-${d.lat}-${d.lon}", position = NaverLatLng(d.lat, d.lon)),
                    captionText = "도착",
                    iconTintColor = DestRed,
                )
            }
        }

        TopBar(state, viewModel, Modifier.align(Alignment.TopCenter))
        BottomPanel(state, viewModel, Modifier.align(Alignment.BottomCenter))

        if (state.searchOpen) SearchOverlay(state, viewModel)
    }
}

@Composable
private fun TopBar(state: ShadeUiState, vm: ShadeViewModel, modifier: Modifier) {
    Card(
        modifier = modifier.fillMaxWidth().statusBarsPadding().padding(12.dp),
        shape = RoundedCornerShape(14.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 6.dp),
    ) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            EndField("출발", state.originLabel.ifBlank { "출발지 검색 · 또는 지도 탭" }, state.origin != null, OriginBlue) {
                vm.openSearch(PickTarget.ORIGIN)
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                HorizontalDivider(Modifier.weight(1f))
                IconButton(onClick = vm::swapEnds) {
                    Icon(Icons.Filled.SwapVert, contentDescription = "출발↔도착")
                }
                HorizontalDivider(Modifier.weight(1f))
            }
            EndField("도착", state.destLabel.ifBlank { "도착지 검색 · 또는 지도 탭" }, state.dest != null, DestRed) {
                vm.openSearch(PickTarget.DEST)
            }
            // 지도 탭 대상 표시
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically) {
                Text("지도 탭 지정:", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.outline)
                FilterChip(selected = state.pickTarget == PickTarget.ORIGIN, onClick = { vm.setPickTarget(PickTarget.ORIGIN) }, label = { Text("출발") })
                FilterChip(selected = state.pickTarget == PickTarget.DEST, onClick = { vm.setPickTarget(PickTarget.DEST) }, label = { Text("도착") })
            }
        }
    }
}

@Composable
private fun EndField(tag: String, label: String, filled: Boolean, dot: Color, onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().clickable(onClick = onClick).padding(vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Box(Modifier.size(10.dp).background(dot, RoundedCornerShape(5.dp)))
        Text(tag, fontWeight = FontWeight.Bold, modifier = Modifier.width(36.dp))
        Text(
            label,
            color = if (filled) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.outline,
            maxLines = 1,
            modifier = Modifier.weight(1f),
        )
        Icon(Icons.Filled.Search, contentDescription = null, tint = MaterialTheme.colorScheme.outline)
    }
}

@Composable
private fun BottomPanel(state: ShadeUiState, vm: ShadeViewModel, modifier: Modifier) {
    Surface(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(topStart = 18.dp, topEnd = 18.dp),
        tonalElevation = 3.dp,
        shadowElevation = 10.dp,
    ) {
        Column(
            Modifier.fillMaxWidth().navigationBarsPadding().padding(16.dp)
                .heightIn(max = 360.dp).verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text("출발 ${state.departHour}시", fontWeight = FontWeight.Bold)
            Slider(
                value = state.departHour.toFloat(),
                onValueChange = { vm.onDepartHour(it.toInt()) },
                valueRange = 0f..23f, steps = 22,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(state.mode == "walk", { vm.onMode("walk") }, label = { Text("도보") })
                FilterChip(state.mode == "bike", { vm.onMode("bike") }, label = { Text("자전거") })
                Spacer(Modifier.width(8.dp))
                FilterChip(state.prefer == "shade", { vm.onPrefer("shade") }, label = { Text("여름·그늘") })
                FilterChip(state.prefer == "sun", { vm.onPrefer("sun") }, label = { Text("겨울·햇빛") })
            }

            when (val r = state.routes) {
                is RoutesUiResult.Idle -> Text(
                    "출발·도착을 지정하면 그늘 경로를 보여줘요.",
                    style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.outline,
                )
                is RoutesUiResult.Loading -> Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Center) {
                    CircularProgressIndicator()
                }
                is RoutesUiResult.Error -> Text("오류: ${r.message}", color = MaterialTheme.colorScheme.error)
                is RoutesUiResult.Success -> {
                    r.response.weather?.let { WeatherRow(it) }
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                        r.response.options.forEachIndexed { i, opt ->
                            OptionCard(opt, i == state.selectedOption, { vm.selectOption(i) }, Modifier.weight(1f))
                        }
                    }
                }
            }
        }
    }
}

private fun optionLabel(name: String): String = when (name) {
    "shortest" -> "최단"; "balanced" -> "균형"; "shadiest" -> "그늘 최적"; "sunniest" -> "햇빛 최적"; else -> name
}

@Composable
private fun OptionCard(opt: RouteOptionOut, selected: Boolean, onClick: () -> Unit, modifier: Modifier) {
    Card(
        modifier = modifier.clickable(onClick = onClick),
        colors = CardDefaults.cardColors(
            containerColor = if (selected) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceVariant,
        ),
    ) {
        Column(Modifier.fillMaxWidth().padding(10.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(optionLabel(opt.name), fontWeight = if (selected) FontWeight.Bold else FontWeight.Normal)
            Text("그늘 ${opt.shadePercent}%", fontSize = 16.sp, fontWeight = FontWeight.Bold)
            Text("${opt.distanceM.toInt()}m · 쾌적 ${opt.comfort.toInt()}", style = MaterialTheme.typography.labelSmall)
        }
    }
}

@Composable
private fun WeatherRow(w: WeatherBadge) {
    val parts = buildList {
        w.tempC?.let { add("${it}°C") }
        w.uvIndex?.let { add("UV ${it}") }
        if (w.heatAdvisory) add("폭염주의")
    }
    if (parts.isNotEmpty()) {
        Text(parts.joinToString("  ·  "), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.secondary)
    }
}

@Composable
private fun SearchOverlay(state: ShadeUiState, vm: ShadeViewModel) {
    Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(Modifier.fillMaxSize().statusBarsPadding().padding(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = vm::closeSearch) {
                    Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "닫기")
                }
                OutlinedTextField(
                    value = state.searchQuery,
                    onValueChange = vm::onSearchQuery,
                    placeholder = { Text(if (state.searchTarget == PickTarget.ORIGIN) "출발지 검색" else "도착지 검색") },
                    singleLine = true,
                    keyboardActions = KeyboardActions(),
                    modifier = Modifier.weight(1f),
                )
            }
            Spacer(Modifier.padding(4.dp))
            if (state.searching) {
                Row(Modifier.fillMaxWidth().padding(16.dp), horizontalArrangement = Arrangement.Center) {
                    CircularProgressIndicator()
                }
            }
            LazyColumn(Modifier.fillMaxWidth()) {
                items(state.searchResults) { r ->
                    ResultRow(r) { vm.onSelectResult(r) }
                    HorizontalDivider()
                }
            }
            if (!state.searching && state.searchResults.isEmpty() && state.searchQuery.isNotBlank()) {
                Text("검색 결과가 없어요. (강남 권역만 지원)", color = MaterialTheme.colorScheme.outline, modifier = Modifier.padding(12.dp))
            }
        }
    }
}

@Composable
private fun ResultRow(r: PlaceResult, onClick: () -> Unit) {
    Column(Modifier.fillMaxWidth().clickable(onClick = onClick).padding(vertical = 12.dp, horizontal = 4.dp)) {
        Text(r.name, fontWeight = FontWeight.Bold, maxLines = 1)
        r.address?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.outline, maxLines = 1) }
    }
}
