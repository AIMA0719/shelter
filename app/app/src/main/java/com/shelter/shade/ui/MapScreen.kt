@file:OptIn(ExperimentalNaverMapApi::class)

package com.shelter.shade.ui

import android.Manifest
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateContentSize
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
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
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Slider
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.MyLocation
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.SwapVert
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
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
import com.shelter.shade.data.LocationProvider
import com.shelter.shade.data.PlaceResult
import com.shelter.shade.data.RouteOptionOut
import com.shelter.shade.data.WeatherBadge
import com.shelter.shade.ui.theme.ShadeGreen
import com.shelter.shade.ui.theme.SunOrange
import com.shelter.shade.util.GeoFormat
import kotlinx.coroutines.launch

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

    // 지도를 탭하면 상·하단 뷰가 사라지고(몰입 모드), 다시 탭하면 돌아온다.
    var chromeVisible by remember { mutableStateOf(true) }
    // 평소엔 작은 검색바, 누르면 출발·도착 입력으로 확장.
    var searchExpanded by remember { mutableStateOf(false) }

    // 위치 권한 + 현재 위치.
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var hasLocationPermission by remember { mutableStateOf(LocationProvider.hasPermission(context)) }
    val permLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions(),
    ) { result -> hasLocationPermission = result.values.any { it } }

    // 앱 시작 시 위치 권한 요청.
    LaunchedEffect(Unit) {
        if (!hasLocationPermission) {
            permLauncher.launch(
                arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION),
            )
        }
    }
    // 권한이 생기면 현재 위치를 출발지로(앱 시작 시 1회). 카메라는 아래 origin effect 가 이동.
    LaunchedEffect(hasLocationPermission) {
        if (hasLocationPermission && state.origin == null) {
            LocationProvider.current(context)?.let { viewModel.setOriginToCurrent(it) }
        }
    }
    // '내 위치' 버튼: 어디서든 현재 위치로 카메라 이동(권한 없으면 요청).
    val onMyLocation: () -> Unit = {
        if (hasLocationPermission) {
            scope.launch {
                LocationProvider.current(context)?.let {
                    camera.animate(CameraUpdate.scrollAndZoomTo(NaverLatLng(it.lat, it.lon), 16.0))
                }
            }
        } else {
            permLauncher.launch(
                arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION),
            )
        }
    }

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
            onMapClick = { _, _ ->
                chromeVisible = !chromeVisible
                if (!chromeVisible) searchExpanded = false
            },
            // 길게 누르면 그 좌표를 출발/도착으로 지정(검색이 못 찾는 골목·공원 입구 등).
            onMapLongClick = { _, coord ->
                viewModel.setPointFromMap(com.shelter.shade.data.LatLng(coord.latitude, coord.longitude))
            },
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

        AnimatedVisibility(
            visible = chromeVisible,
            enter = slideInVertically(tween(300)) { -it } + fadeIn(tween(300)),
            exit = slideOutVertically(tween(300)) { -it } + fadeOut(tween(300)),
            modifier = Modifier.align(Alignment.TopCenter),
        ) {
            TopBar(state, viewModel, searchExpanded, { searchExpanded = it }, Modifier)
        }

        // 하단: '내 위치' 버튼(항상 표시) + 그늘 패널(몰입 모드 시 슬라이드). 패널이 줄어들면
        // 컬럼이 짧아져 버튼이 자연스럽게 아래로 따라 내려가고, 다시 펴지면 위로 올라온다.
        Column(Modifier.align(Alignment.BottomCenter)) {
            Row(
                Modifier.fillMaxWidth().padding(end = 16.dp, bottom = 12.dp),
                horizontalArrangement = Arrangement.End,
            ) {
                FloatingActionButton(
                    onClick = onMyLocation,
                    containerColor = MaterialTheme.colorScheme.surface,
                ) {
                    Icon(Icons.Filled.MyLocation, contentDescription = "내 위치", tint = OriginBlue)
                }
            }
            AnimatedVisibility(
                visible = chromeVisible,
                enter = slideInVertically(tween(300)) { it } + expandVertically(tween(300)) + fadeIn(tween(300)),
                exit = slideOutVertically(tween(300)) { it } + shrinkVertically(tween(300)) + fadeOut(tween(300)),
            ) {
                BottomPanel(state, viewModel, Modifier)
            }
        }

        if (state.searchOpen) SearchOverlay(state, viewModel)
    }
}

@Composable
private fun TopBar(
    state: ShadeUiState,
    vm: ShadeViewModel,
    expanded: Boolean,
    onExpandedChange: (Boolean) -> Unit,
    modifier: Modifier,
) {
    Card(
        modifier = modifier.fillMaxWidth().statusBarsPadding().padding(12.dp),
        shape = RoundedCornerShape(14.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 6.dp),
    ) {
        Column(
            Modifier.padding(12.dp).animateContentSize(tween(300)),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            if (!expanded) {
                CollapsedSearchBar(state) { onExpandedChange(true) }
            } else {
                EndField("출발", state.originLabel.ifBlank { "출발지 검색" }, state.origin != null, OriginBlue) {
                    vm.openSearch(PickTarget.ORIGIN)
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    HorizontalDivider(Modifier.weight(1f))
                    IconButton(onClick = vm::swapEnds) {
                        Icon(Icons.Filled.SwapVert, contentDescription = "출발↔도착")
                    }
                    HorizontalDivider(Modifier.weight(1f))
                }
                EndField("도착", state.destLabel.ifBlank { "도착지 검색" }, state.dest != null, DestRed) {
                    vm.openSearch(PickTarget.DEST)
                }
            }
        }
    }
}

@Composable
private fun CollapsedSearchBar(state: ShadeUiState, onClick: () -> Unit) {
    val hasEnds = state.origin != null || state.dest != null
    val summary = when {
        state.origin != null && state.dest != null -> "${state.originLabel} → ${state.destLabel}"
        state.origin != null -> "출발: ${state.originLabel}"
        state.dest != null -> "도착: ${state.destLabel}"
        else -> "출발지·도착지 검색"
    }
    Row(
        Modifier.fillMaxWidth().clickable(onClick = onClick).padding(vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Icon(Icons.Filled.Search, contentDescription = null, tint = MaterialTheme.colorScheme.outline)
        Text(
            summary,
            color = if (hasEnds) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.outline,
            maxLines = 1,
            modifier = Modifier.weight(1f),
        )
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
                .heightIn(max = 420.dp).verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            // 지도의 초록/주황 선이 무엇인지 알려주는 범례(핵심 시각 언어 해독).
            Legend()

            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("출발 ${state.departHour}시", fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                FilterChip(selected = false, onClick = vm::onNow, label = { Text("지금") })
            }
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
                    "출발·도착을 지정하면 그늘 경로를 보여줘요. (지도를 길게 눌러도 지정돼요)",
                    style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.outline,
                )
                is RoutesUiResult.Loading -> Column(
                    Modifier.fillMaxWidth(),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    CircularProgressIndicator()
                    Text(
                        "경로를 계산 중… 서버를 깨우는 중이면 최대 1분 걸릴 수 있어요.",
                        style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.outline,
                    )
                }
                is RoutesUiResult.Error -> Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Text(r.message, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium)
                    TextButton(onClick = vm::planRoutes, contentPadding = androidx.compose.foundation.layout.PaddingValues(0.dp)) {
                        Text("다시 시도")
                    }
                }
                is RoutesUiResult.TooFar -> Text(
                    "경로가 너무 멀어요 — 약 %.1fkm (최대 %dkm).\n중간 지점을 도착지로 정해 나눠서 검색해 주세요."
                        .format(r.distanceM / 1000.0, (r.capM / 1000).toInt()),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.secondary,
                )
                is RoutesUiResult.Success -> {
                    r.response.weather?.let { WeatherRow(it) }
                    if (r.response.options.isEmpty()) {
                        Text(
                            "경로를 찾지 못했어요. 다른 출발·도착 지점을 시도해 주세요.",
                            style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.secondary,
                        )
                    } else {
                        val recommended = if (state.prefer == "sun") "sunniest" else "shadiest"
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                            r.response.options.forEachIndexed { i, opt ->
                                OptionCard(
                                    opt = opt,
                                    selected = i == state.selectedOption,
                                    recommended = opt.name == recommended,
                                    onClick = { vm.selectOption(i) },
                                    modifier = Modifier.weight(1f),
                                )
                            }
                        }
                        val note = if (r.response.routing == "grid") " · 대략 경로" else ""
                        Text(
                            "추정치 · 건물 그림자 기준$note",
                            style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.outline,
                        )
                    }
                }
            }

            // 출발/도착이 정해지면 '시원한(겨울엔 햇빛 좋은) 출발 시각'을 추천한다.
            DepartureSection(state, vm)
        }
    }
}

@Composable
private fun Legend() {
    Row(horizontalArrangement = Arrangement.spacedBy(16.dp), verticalAlignment = Alignment.CenterVertically) {
        Swatch(ShadeGreen, "그늘")
        Swatch(SunOrange, "햇빛")
    }
}

@Composable
private fun Swatch(color: Color, label: String) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        Box(Modifier.size(12.dp).background(color, RoundedCornerShape(6.dp)))
        Text(label, style = MaterialTheme.typography.labelMedium)
    }
}

private fun optionLabel(name: String): String = when (name) {
    "shortest" -> "최단"; "balanced" -> "균형"; "shadiest" -> "그늘 최적"; "sunniest" -> "햇빛 최적"; else -> name
}

@Composable
private fun OptionCard(
    opt: RouteOptionOut,
    selected: Boolean,
    recommended: Boolean,
    onClick: () -> Unit,
    modifier: Modifier,
) {
    Card(
        modifier = modifier.clickable(onClick = onClick),
        colors = CardDefaults.cardColors(
            containerColor = if (selected) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceVariant,
        ),
    ) {
        Column(Modifier.fillMaxWidth().padding(10.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            if (recommended) {
                Text("추천", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary)
            }
            Text(optionLabel(opt.name), fontWeight = if (selected) FontWeight.Bold else FontWeight.Normal, maxLines = 1)
            Text("그늘 ${opt.shadePercent}%", fontSize = 16.sp, fontWeight = FontWeight.Bold)
            val meta = buildString {
                append(GeoFormat.distance(opt.distanceM))
                if (opt.durationMin > 0.0) append(" · ${GeoFormat.duration(opt.durationMin)}")
            }
            Text(meta, style = MaterialTheme.typography.labelSmall)
            Text("쾌적 ${opt.comfort.toInt()}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.secondary)
        }
    }
}

@Composable
private fun DepartureSection(state: ShadeUiState, vm: ShadeViewModel) {
    if (state.origin == null || state.dest == null) return
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        HorizontalDivider()
        val label = if (state.prefer == "sun") "햇빛 좋은 출발 시간 추천" else "시원한 출발 시간 추천"
        Button(onClick = vm::suggestDeparture, modifier = Modifier.fillMaxWidth()) { Text(label) }
        when (val d = state.departure) {
            is DepartureUiResult.Idle -> {}
            is DepartureUiResult.Loading -> Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Center) {
                CircularProgressIndicator(Modifier.size(28.dp))
            }
            is DepartureUiResult.Error -> Text("추천 실패: ${d.message}", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium)
            is DepartureUiResult.Success -> DepartureResult(d.response, state.departHour, vm)
        }
    }
}

@Composable
private fun DepartureResult(
    resp: com.shelter.shade.data.DepartureSuggestResponse,
    currentHour: Int,
    vm: ShadeViewModel,
) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        val bestHour = hourOf(resp.best.departTime)
        Text(
            "${bestHour?.let { hourLabel(it) } ?: "추천"} 출발 · 그늘 ${resp.best.shadePercent}%",
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.primary,
        )
        Row(
            Modifier.horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            resp.candidates.forEach { c ->
                val h = hourOf(c.departTime)
                FilterChip(
                    selected = h == currentHour,
                    onClick = { h?.let { vm.onDepartHour(it) } },
                    label = { Text("${h ?: "?"}시 ${c.shadePercent.toInt()}%") },
                )
            }
        }
    }
}

/** ISO(예: 2026-07-15T08:00+09:00)에서 시(hour)만 뽑는다. */
private fun hourOf(iso: String): Int? = iso.substringAfter('T', "").take(2).toIntOrNull()

private fun hourLabel(h: Int): String {
    val ampm = if (h < 12) "오전" else "오후"
    val h12 = if (h % 12 == 0) 12 else h % 12
    return "$ampm ${h12}시"
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
                Text("검색 결과가 없어요. (서울 지역만 지원)", color = MaterialTheme.colorScheme.outline, modifier = Modifier.padding(12.dp))
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
