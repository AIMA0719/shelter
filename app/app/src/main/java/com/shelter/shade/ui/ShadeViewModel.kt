package com.shelter.shade.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.shelter.shade.data.DepartureSuggestResponse
import com.shelter.shade.data.LatLng
import com.shelter.shade.data.PlaceResult
import com.shelter.shade.data.PlaceSearch
import com.shelter.shade.data.RoutesResponse
import com.shelter.shade.engine.LocalShadeEngine
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.time.LocalDate
import java.time.LocalTime
import java.time.OffsetDateTime
import java.time.ZoneOffset

enum class PickTarget { ORIGIN, DEST }

sealed interface RoutesUiResult {
    data object Idle : RoutesUiResult
    data object Loading : RoutesUiResult
    data class Success(val response: RoutesResponse) : RoutesUiResult
    data class Error(val message: String) : RoutesUiResult
}

sealed interface DepartureUiResult {
    data object Idle : DepartureUiResult
    data object Loading : DepartureUiResult
    data class Success(val response: DepartureSuggestResponse) : DepartureUiResult
    data class Error(val message: String) : DepartureUiResult
}

data class ShadeUiState(
    val origin: LatLng? = null,
    val originLabel: String = "",
    val dest: LatLng? = null,
    val destLabel: String = "",
    val pickTarget: PickTarget = PickTarget.ORIGIN, // 지도 탭이 지정할 대상
    val departHour: Int = 14,
    val mode: String = "walk",
    val prefer: String = "shade",
    val routes: RoutesUiResult = RoutesUiResult.Idle,
    val selectedOption: Int = 0,
    val departure: DepartureUiResult = DepartureUiResult.Idle,
    // 검색 오버레이
    val searchOpen: Boolean = false,
    val searchTarget: PickTarget = PickTarget.ORIGIN,
    val searchQuery: String = "",
    val searchResults: List<PlaceResult> = emptyList(),
    val searching: Boolean = false,
)

private val KST: ZoneOffset = ZoneOffset.ofHours(9)
// 강남 권역(데이터 범위)로 검색 바이어스: [minLon, minLat, maxLon, maxLat]
private val GANGNAM_VIEWBOX = doubleArrayOf(127.020, 37.488, 127.045, 37.508)

class ShadeViewModel(application: Application) : AndroidViewModel(application) {

    private val _state = MutableStateFlow(ShadeUiState())
    val state: StateFlow<ShadeUiState> = _state.asStateFlow()

    private val engine: LocalShadeEngine by lazy { LocalShadeEngine.get(getApplication()) }
    private var searchJob: Job? = null
    private var planJob: Job? = null

    // --- 지점 지정(지도 탭) ---
    fun onMapTap(lat: Double, lon: Double) {
        val target = _state.value.pickTarget
        val ll = LatLng(lat, lon)
        if (target == PickTarget.ORIGIN) {
            _state.update { it.copy(origin = ll, originLabel = "지정한 위치", pickTarget = PickTarget.DEST) }
        } else {
            _state.update { it.copy(dest = ll, destLabel = "지정한 위치") }
        }
        reverseLabel(target, ll)
        maybeAutoPlan()
    }

    fun setPickTarget(target: PickTarget) = _state.update { it.copy(pickTarget = target) }

    private fun reverseLabel(target: PickTarget, ll: LatLng) {
        viewModelScope.launch {
            val name = withContext(Dispatchers.IO) { PlaceSearch.reverse(ll.lat, ll.lon) } ?: return@launch
            _state.update {
                if (target == PickTarget.ORIGIN) it.copy(originLabel = name) else it.copy(destLabel = name)
            }
        }
    }

    // --- 검색 ---
    fun openSearch(target: PickTarget) =
        _state.update { it.copy(searchOpen = true, searchTarget = target, searchQuery = "", searchResults = emptyList()) }

    fun closeSearch() = _state.update { it.copy(searchOpen = false) }

    fun onSearchQuery(q: String) {
        _state.update { it.copy(searchQuery = q) }
        searchJob?.cancel()
        if (q.isBlank()) {
            _state.update { it.copy(searchResults = emptyList(), searching = false) }
            return
        }
        val target = _state.value.searchTarget
        searchJob = viewModelScope.launch {
            delay(250) // 디바운스
            _state.update { it.copy(searching = true) }
            val results = runCatching { PlaceSearch.search(q, GANGNAM_VIEWBOX) }.getOrDefault(emptyList())
            // 응답이 도착했을 때도 여전히 같은 쿼리/대상일 때만 반영(오래된 응답 무시)
            _state.update {
                if (it.searchQuery == q && it.searchTarget == target) it.copy(searchResults = results, searching = false) else it
            }
        }
    }

    fun onSelectResult(r: PlaceResult) {
        val ll = LatLng(r.lat, r.lon)
        _state.update {
            val s = if (it.searchTarget == PickTarget.ORIGIN) {
                it.copy(origin = ll, originLabel = r.name, pickTarget = PickTarget.DEST)
            } else {
                it.copy(dest = ll, destLabel = r.name)
            }
            s.copy(searchOpen = false)
        }
        maybeAutoPlan()
    }

    // --- 옵션/설정 ---
    fun onDepartHour(v: Int) {
        _state.update { it.copy(departHour = v.coerceIn(0, 23)) }
        maybeAutoPlan()
    }
    fun onMode(mode: String) {
        _state.update { it.copy(mode = mode) }
        maybeAutoPlan()
    }
    fun onPrefer(prefer: String) {
        _state.update { it.copy(prefer = prefer) }
        maybeAutoPlan()
    }
    fun selectOption(index: Int) = _state.update { it.copy(selectedOption = index) }

    fun swapEnds() = _state.update {
        it.copy(origin = it.dest, originLabel = it.destLabel, dest = it.origin, destLabel = it.originLabel)
    }.also { maybeAutoPlan() }

    private fun maybeAutoPlan() {
        val s = _state.value
        if (s.origin != null && s.dest != null) planRoutes()
    }

    fun planRoutes() {
        val s = _state.value
        val origin = s.origin
        val dest = s.dest
        if (origin == null || dest == null) {
            _state.update { it.copy(routes = RoutesUiResult.Error("출발지와 도착지를 지정하세요.")) }
            return
        }
        _state.update { it.copy(routes = RoutesUiResult.Loading, selectedOption = 0) }
        // 직전 계산을 취소 — 슬라이더/토글 연타 시 오래된 결과가 최신을 덮어쓰지 않게.
        planJob?.cancel()
        planJob = viewModelScope.launch {
            val resp = try {
                val odt = departOdt(s.departHour)
                withContext(Dispatchers.Default) {
                    engine.planRoutes(origin, dest, odt.toInstant().toEpochMilli(), odt.toString(), s.mode, s.prefer)
                }
            } catch (c: CancellationException) {
                throw c // 취소는 전파(상태를 건드리지 않음)
            } catch (e: Exception) {
                _state.update { it.copy(routes = RoutesUiResult.Error(e.message ?: "계산 실패")) }
                return@launch
            }
            _state.update { it.copy(routes = RoutesUiResult.Success(resp)) }
        }
    }

    fun suggestDeparture() {
        val s = _state.value
        val origin = s.origin
        val dest = s.dest
        if (origin == null || dest == null) {
            _state.update { it.copy(departure = DepartureUiResult.Error("출발지와 도착지를 지정하세요.")) }
            return
        }
        _state.update { it.copy(departure = DepartureUiResult.Loading) }
        viewModelScope.launch {
            val r = runCatching {
                withContext(Dispatchers.Default) {
                    engine.suggestDeparture(origin, dest, java.time.Instant.now().toEpochMilli(), s.mode, s.prefer)
                }
            }
            _state.update {
                it.copy(
                    departure = r.fold(
                        onSuccess = { resp -> DepartureUiResult.Success(resp) },
                        onFailure = { e -> DepartureUiResult.Error(e.message ?: "계산 실패") },
                    )
                )
            }
        }
    }

    private fun departOdt(hour: Int): OffsetDateTime =
        OffsetDateTime.of(LocalDate.now(KST), LocalTime.of(hour, 0), KST)
}
