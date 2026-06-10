package com.shelter.shade.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.shelter.shade.data.DepartureSuggestResponse
import com.shelter.shade.data.LatLng
import com.shelter.shade.data.PlaceResult
import com.shelter.shade.data.PlaceSearch
import com.shelter.shade.data.RoutesResponse
import com.shelter.shade.data.ShadeRepository
import com.shelter.shade.data.UserPrefs
import com.shelter.shade.engine.LocalShadeEngine
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collect
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
    /** 출발-도착 직선거리가 모드별 상한을 넘어 계산하지 않음(중간 지점 경유 유도). */
    data class TooFar(val distanceM: Double, val capM: Double) : RoutesUiResult
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
    // 마지막 제출이 완료됐는지 — '결과 없음' 안내를 타이핑 중이 아니라 검색 후에만 보여준다.
    val searchSubmitted: Boolean = false,
    // 즐겨찾기·최근검색(DataStore 동기화). null=로딩 전(온보딩 게이트가 깜빡이지 않도록).
    val favorites: List<PlaceResult> = emptyList(),
    val recents: List<PlaceResult> = emptyList(),
    val onboardingComplete: Boolean? = null,
)

private val KST: ZoneOffset = ZoneOffset.ofHours(9)
// 서울 전역(건물 데이터 범위)으로 검색 제한: [minLon, minLat, maxLon, maxLat]
private val SEOUL_VIEWBOX = doubleArrayOf(126.76, 37.41, 127.19, 37.70)
// 출발-도착 직선거리 상한(이 이상은 도보/자전거로 비현실적 + 무료 서버 계산 과부하).
// 더 멀면 중간 지점을 거쳐 나눠서 검색하도록 안내한다.
private const val WALK_MAX_ROUTE_M = 6_000.0
private const val BIKE_MAX_ROUTE_M = 10_000.0
// 최근 검색은 최신 N개만 보관(오래된 것은 밀려난다).
private const val MAX_RECENTS = 8

class ShadeViewModel(application: Application) : AndroidViewModel(application) {

    private val _state = MutableStateFlow(ShadeUiState())
    val state: StateFlow<ShadeUiState> = _state.asStateFlow()

    // 서울 전역은 서버(PostGIS), 서버 실패 시 강남 권역은 온디바이스 엔진으로 폴백.
    private val repo = ShadeRepository()
    private val engine: LocalShadeEngine by lazy { LocalShadeEngine.get(getApplication()) }
    private val prefs = UserPrefs(application)
    private var searchJob: Job? = null
    private var planJob: Job? = null
    private var suggestJob: Job? = null

    /**
     * 출발시간 추천은 출발/도착/모드/선호(여름·겨울)에 종속된다. 이들이 바뀌면 이전
     * 경로 기준의 추천이 화면에 남아 '엉뚱한 경로의 추천'으로 보이므로 즉시 비운다
     * (진행 중 요청도 취소). departHour 변경은 추천 자체에 영향이 없으므로 제외.
     */
    private fun invalidateDepartureSuggestion() {
        suggestJob?.cancel()
        _state.update { if (it.departure == DepartureUiResult.Idle) it else it.copy(departure = DepartureUiResult.Idle) }
    }

    init {
        // 출발 시각 기본값 = 현재 시각의 정각(분·초는 버림). departOdt 가 분/초를 0 으로 만든다.
        _state.update { it.copy(departHour = OffsetDateTime.now(KST).hour) }
        // DataStore → 상태. 영속 데이터를 단일 출처로 삼아 화면이 항상 저장값을 반영하게 한다.
        viewModelScope.launch { prefs.onboardingDone.collect { done -> _state.update { it.copy(onboardingComplete = done) } } }
        viewModelScope.launch { prefs.favorites.collect { f -> _state.update { it.copy(favorites = f) } } }
        viewModelScope.launch { prefs.recents.collect { r -> _state.update { it.copy(recents = r) } } }
    }

    // --- 온보딩 ---
    fun completeOnboarding() = viewModelScope.launch { prefs.setOnboardingDone(true) }
    /** 설정 → '온보딩 다시 보기'. */
    fun resetOnboarding() = viewModelScope.launch { prefs.setOnboardingDone(false) }

    // --- 즐겨찾기 / 최근 검색 ---
    /** 같은 장소 판별 — 좌표 기준(이름/주소 표기 차이는 무시). */
    private fun samePlace(a: PlaceResult, b: PlaceResult): Boolean =
        kotlin.math.abs(a.lat - b.lat) < 1e-6 && kotlin.math.abs(a.lon - b.lon) < 1e-6

    fun isFavorite(p: PlaceResult): Boolean = _state.value.favorites.any { samePlace(it, p) }

    fun toggleFavorite(p: PlaceResult) {
        val cur = _state.value.favorites
        val next = if (cur.any { samePlace(it, p) }) cur.filterNot { samePlace(it, p) }
                   else listOf(p) + cur
        viewModelScope.launch { prefs.setFavorites(next) }
    }

    fun removeRecent(p: PlaceResult) {
        viewModelScope.launch { prefs.setRecents(_state.value.recents.filterNot { samePlace(it, p) }) }
    }

    /** 검색 결과를 선택할 때 호출 — 최신을 맨 앞에 두고 중복 제거, 최대 [MAX_RECENTS]개. */
    private fun recordRecent(p: PlaceResult) {
        val next = (listOf(p) + _state.value.recents.filterNot { samePlace(it, p) }).take(MAX_RECENTS)
        viewModelScope.launch { prefs.setRecents(next) }
    }

    // --- 현재 위치 ---
    /** 현재 위치를 출발지로 지정(앱 시작 시 자동 + '내 위치' 버튼). */
    fun setOriginToCurrent(ll: LatLng) {
        _state.update { it.copy(origin = ll, originLabel = "내 위치") }
        invalidateDepartureSuggestion()
        maybeAutoPlan()
    }

    // --- 검색 ---
    fun openSearch(target: PickTarget) =
        _state.update { it.copy(searchOpen = true, searchTarget = target, searchQuery = "", searchResults = emptyList(), searchSubmitted = false) }

    fun closeSearch() = _state.update { it.copy(searchOpen = false) }

    /** 입력 텍스트 갱신 + 이전 질의 결과 비우기. 질의는 명시적 제출([onSearchSubmit])에서만
     *  나간다 — Nominatim 정책이 키 입력마다 질의하는 자동완성을 금지하기 때문(프록시 경유여도
     *  동일). 결과를 남겨두면 수정된 검색어 아래 이전 검색어의 결과가 선택될 수 있어 즉시 비운다. */
    fun onSearchQuery(q: String) {
        searchJob?.cancel()
        _state.update {
            it.copy(searchQuery = q, searchResults = emptyList(), searching = false, searchSubmitted = false)
        }
    }

    /** 키보드 검색 액션/검색 버튼 → 실제 지오코딩 질의. */
    fun onSearchSubmit() {
        val q = _state.value.searchQuery
        if (q.isBlank()) return
        val target = _state.value.searchTarget
        searchJob?.cancel()
        searchJob = viewModelScope.launch {
            _state.update { it.copy(searching = true) }
            val results = runCatching { PlaceSearch.search(q, SEOUL_VIEWBOX) }.getOrDefault(emptyList())
            // 응답이 도착했을 때도 여전히 같은 쿼리/대상일 때만 반영(오래된 응답 무시)
            _state.update {
                if (it.searchQuery == q && it.searchTarget == target) {
                    it.copy(searchResults = results, searching = false, searchSubmitted = true)
                } else it
            }
        }
    }

    fun onSelectResult(r: PlaceResult) {
        recordRecent(r)
        val ll = LatLng(r.lat, r.lon)
        _state.update {
            val s = if (it.searchTarget == PickTarget.ORIGIN) {
                it.copy(origin = ll, originLabel = r.name)
            } else {
                it.copy(dest = ll, destLabel = r.name)
            }
            s.copy(searchOpen = false)
        }
        invalidateDepartureSuggestion()
        maybeAutoPlan()
    }

    // --- 지도에서 지점 선택 ---
    /**
     * 지도를 길게 눌러 좌표로 출발/도착을 지정한다(PRD P0 입력 방식). 출발지가 없으면
     * 출발지로, 있으면 도착지로 채운다. 역지오코딩으로 라벨을 보완(검색이 못 찾는
     * 골목·공원 입구 등도 지정 가능). 검색이 끝나기 전엔 임시 라벨을 보여준다.
     */
    fun setPointFromMap(ll: LatLng) {
        val target = if (_state.value.origin == null) PickTarget.ORIGIN else PickTarget.DEST
        _state.update {
            if (target == PickTarget.ORIGIN) it.copy(origin = ll, originLabel = "지도에서 선택한 위치")
            else it.copy(dest = ll, destLabel = "지도에서 선택한 위치")
        }
        viewModelScope.launch {
            val label = runCatching {
                withContext(Dispatchers.IO) { PlaceSearch.reverse(ll.lat, ll.lon) }
            }.getOrNull()?.let(::shortLabel)
            if (!label.isNullOrBlank()) {
                // 그 사이 사용자가 같은 끝점을 다른 좌표로 바꾸지 않았을 때만 라벨 반영.
                _state.update {
                    when (target) {
                        PickTarget.ORIGIN -> if (it.origin == ll) it.copy(originLabel = label) else it
                        PickTarget.DEST -> if (it.dest == ll) it.copy(destLabel = label) else it
                    }
                }
            }
        }
        invalidateDepartureSuggestion()
        maybeAutoPlan()
    }

    private fun shortLabel(displayName: String): String =
        displayName.split(",").map { it.trim() }.filter { it.isNotEmpty() }.take(2).joinToString(" ")

    // --- 옵션/설정 ---
    fun onDepartHour(v: Int) {
        _state.update { it.copy(departHour = v.coerceIn(0, 23)) }
        maybeAutoPlan()
    }

    /** '지금' — 출발 시각을 현재 정각으로 되돌린다. */
    fun onNow() = onDepartHour(OffsetDateTime.now(KST).hour)
    fun onMode(mode: String) {
        _state.update { it.copy(mode = mode) }
        invalidateDepartureSuggestion()
        maybeAutoPlan()
    }
    fun onPrefer(prefer: String) {
        _state.update { it.copy(prefer = prefer) }
        invalidateDepartureSuggestion()
        maybeAutoPlan()
    }
    fun selectOption(index: Int) = _state.update { it.copy(selectedOption = index) }

    fun swapEnds() {
        _state.update {
            it.copy(origin = it.dest, originLabel = it.destLabel, dest = it.origin, destLabel = it.originLabel)
        }
        invalidateDepartureSuggestion()
        maybeAutoPlan()
    }

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
        // 거리 상한 초과면 서버를 부르지 않고 즉시 안내(느린 장거리 계산 회피 + 현실성).
        val distanceM = haversineM(origin, dest)
        val capM = maxRouteM(s.mode)
        if (distanceM > capM) {
            _state.update { it.copy(routes = RoutesUiResult.TooFar(distanceM, capM)) }
            return
        }
        _state.update { it.copy(routes = RoutesUiResult.Loading, selectedOption = 0) }
        // 직전 계산을 취소 — 슬라이더/토글 연타 시 오래된 결과가 최신을 덮어쓰지 않게.
        planJob?.cancel()
        planJob = viewModelScope.launch {
            val odt = departOdt(s.departHour)
            // 1) 서울 전역: 서버(PostGIS) 우선.
            val resp = try {
                withContext(Dispatchers.IO) {
                    repo.fetchRouteOptions(origin, dest, odt.toString(), s.mode, s.prefer)
                }
            } catch (c: CancellationException) {
                throw c // 취소는 전파(상태를 건드리지 않음)
            } catch (server: Exception) {
                // 2) 서버 실패(지연/오프라인). 온디바이스 폴백은 강남 권역 안에서만 의미가 있다.
                //    범위 밖이면 직선·0% 같은 오해 소지 결과 대신 명확히 안내한다.
                if (!engine.covers(origin) || !engine.covers(dest)) {
                    _state.update {
                        it.copy(routes = RoutesUiResult.Error("서버 응답이 지연되고 있어요. 잠시 후 다시 시도해 주세요."))
                    }
                    return@launch
                }
                try {
                    withContext(Dispatchers.Default) {
                        engine.planRoutes(origin, dest, odt.toInstant().toEpochMilli(), odt.toString(), s.mode, s.prefer)
                    }
                } catch (c: CancellationException) {
                    throw c
                } catch (e: Exception) {
                    _state.update { it.copy(routes = RoutesUiResult.Error(e.message ?: "계산 실패")) }
                    return@launch
                }
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
        // 추천이 종속된 경로 입력을 시작 시점에 고정한다. 응답이 늦게 도착했을 때
        // 그 사이 입력이 바뀌었으면 무시해, 바뀐 경로에 엉뚱한 추천이 붙는 것을 막는다.
        val mode = s.mode
        val prefer = s.prefer
        _state.update { it.copy(departure = DepartureUiResult.Loading) }
        suggestJob?.cancel()
        suggestJob = viewModelScope.launch {
            // 입력이 그대로일 때만 상태 반영(취소/스테일 결과가 최신을 덮어쓰지 않게).
            fun applyIfCurrent(result: DepartureUiResult) {
                _state.update {
                    if (it.origin == origin && it.dest == dest && it.mode == mode && it.prefer == prefer) {
                        it.copy(departure = result)
                    } else {
                        it
                    }
                }
            }
            val resp = try {
                withContext(Dispatchers.IO) { repo.suggestDeparture(origin, dest, mode, prefer) }
            } catch (c: CancellationException) {
                throw c // 취소는 전파(상태를 건드리지 않음 — runCatching 처럼 삼키지 않는다)
            } catch (server: Exception) {
                // 서버 실패 → 강남 온디바이스 폴백.
                try {
                    withContext(Dispatchers.Default) {
                        engine.suggestDeparture(origin, dest, java.time.Instant.now().toEpochMilli(), mode, prefer)
                    }
                } catch (c: CancellationException) {
                    throw c
                } catch (e: Exception) {
                    applyIfCurrent(DepartureUiResult.Error(e.message ?: "계산 실패"))
                    return@launch
                }
            }
            applyIfCurrent(DepartureUiResult.Success(resp))
        }
    }

    private fun departOdt(hour: Int): OffsetDateTime =
        OffsetDateTime.of(LocalDate.now(KST), LocalTime.of(hour, 0), KST)

    private fun maxRouteM(mode: String): Double =
        if (mode == "bike") BIKE_MAX_ROUTE_M else WALK_MAX_ROUTE_M

    /** 두 지점 사이 직선거리(m). */
    private fun haversineM(a: LatLng, b: LatLng): Double {
        val radius = 6_371_000.0
        val dLat = Math.toRadians(b.lat - a.lat)
        val dLon = Math.toRadians(b.lon - a.lon)
        val s1 = Math.sin(dLat / 2)
        val s2 = Math.sin(dLon / 2)
        val h = s1 * s1 + Math.cos(Math.toRadians(a.lat)) * Math.cos(Math.toRadians(b.lat)) * s2 * s2
        return radius * 2 * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h))
    }
}
