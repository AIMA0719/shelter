package com.shelter.shade.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.shelter.shade.data.DepartureSuggestResponse
import com.shelter.shade.data.RoutesResponse
import com.shelter.shade.data.ShadeRepository
import com.shelter.shade.data.ShadeResponse
import com.shelter.shade.util.GeoFormat
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.OffsetDateTime
import java.time.ZoneOffset

sealed interface ShadeUiResult {
    data object Idle : ShadeUiResult
    data object Loading : ShadeUiResult
    data class Success(val response: ShadeResponse) : ShadeUiResult
    data class Error(val message: String) : ShadeUiResult
}

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
    val originLat: String = "37.49750",
    val originLon: String = "127.02700",
    val destLat: String = "37.49900",
    val destLon: String = "127.02700",
    val departHour: Int = 16,
    val mode: String = "walk",
    val prefer: String = "shade", // shade=여름(그늘), sun=겨울(햇빛)
    val result: ShadeUiResult = ShadeUiResult.Idle,
    val routes: RoutesUiResult = RoutesUiResult.Idle,
    val selectedOption: Int = 0,
    val departure: DepartureUiResult = DepartureUiResult.Idle,
)

private val KST: ZoneOffset = ZoneOffset.ofHours(9)

class ShadeViewModel(
    private val repository: ShadeRepository = ShadeRepository(),
) : ViewModel() {

    private val _state = MutableStateFlow(ShadeUiState())
    val state: StateFlow<ShadeUiState> = _state.asStateFlow()

    fun onOriginLat(v: String) = _state.update { it.copy(originLat = v) }
    fun onOriginLon(v: String) = _state.update { it.copy(originLon = v) }
    fun onDestLat(v: String) = _state.update { it.copy(destLat = v) }
    fun onDestLon(v: String) = _state.update { it.copy(destLon = v) }
    fun onDepartHour(v: Int) = _state.update { it.copy(departHour = v.coerceIn(0, 23)) }
    fun onMode(mode: String) = _state.update { it.copy(mode = mode) }
    fun onPrefer(prefer: String) = _state.update { it.copy(prefer = prefer) }
    fun selectOption(index: Int) = _state.update { it.copy(selectedOption = index) }

    fun planRoutes() {
        val s = _state.value
        val origin = GeoFormat.parseLatLng(s.originLat, s.originLon)
        val dest = GeoFormat.parseLatLng(s.destLat, s.destLon)
        if (origin == null || dest == null) {
            _state.update { it.copy(routes = RoutesUiResult.Error("좌표 형식이 올바르지 않습니다.")) }
            return
        }
        _state.update { it.copy(routes = RoutesUiResult.Loading, selectedOption = 0) }
        viewModelScope.launch {
            val result = runCatching {
                repository.fetchRouteOptions(origin, dest, departIso(s.departHour), s.mode, s.prefer)
            }
            _state.update {
                it.copy(
                    routes = result.fold(
                        onSuccess = { resp -> RoutesUiResult.Success(resp) },
                        onFailure = { e -> RoutesUiResult.Error(e.message ?: "요청 실패") },
                    )
                )
            }
        }
    }

    fun suggestDeparture() {
        val s = _state.value
        val origin = GeoFormat.parseLatLng(s.originLat, s.originLon)
        val dest = GeoFormat.parseLatLng(s.destLat, s.destLon)
        if (origin == null || dest == null) {
            _state.update { it.copy(departure = DepartureUiResult.Error("좌표 형식이 올바르지 않습니다.")) }
            return
        }
        _state.update { it.copy(departure = DepartureUiResult.Loading) }
        viewModelScope.launch {
            val result = runCatching {
                repository.suggestDeparture(origin, dest, s.mode, s.prefer)
            }
            _state.update {
                it.copy(
                    departure = result.fold(
                        onSuccess = { resp -> DepartureUiResult.Success(resp) },
                        onFailure = { e -> DepartureUiResult.Error(e.message ?: "요청 실패") },
                    )
                )
            }
        }
    }

    fun computeShade() {
        val s = _state.value
        val origin = GeoFormat.parseLatLng(s.originLat, s.originLon)
        val dest = GeoFormat.parseLatLng(s.destLat, s.destLon)
        if (origin == null || dest == null) {
            _state.update { it.copy(result = ShadeUiResult.Error("좌표 형식이 올바르지 않습니다.")) }
            return
        }
        _state.update { it.copy(result = ShadeUiResult.Loading) }
        viewModelScope.launch {
            val result = runCatching {
                repository.fetchRouteShade(origin, dest, departIso(s.departHour), s.mode)
            }
            _state.update {
                it.copy(
                    result = result.fold(
                        onSuccess = { resp -> ShadeUiResult.Success(resp) },
                        onFailure = { e -> ShadeUiResult.Error(e.message ?: "요청 실패") },
                    )
                )
            }
        }
    }

    private fun departIso(hour: Int): String =
        OffsetDateTime.of(LocalDate.now(KST), java.time.LocalTime.of(hour, 0), KST).toString()
}
