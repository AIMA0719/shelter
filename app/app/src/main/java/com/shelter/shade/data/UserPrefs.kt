package com.shelter.shade.data

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

/** 앱 단일 Preferences DataStore. 프로세스당 하나만 존재해야 하므로 Context 확장으로 둔다. */
private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "shelter_prefs")

/**
 * 사용자 환경설정 영속화 — 온보딩 완료 여부, 즐겨찾기, 최근 검색.
 *
 * 즐겨찾기·최근검색은 [PlaceResult] 리스트를 JSON 문자열로 직렬화해 저장한다(별도 테이블이
 * 필요 없을 만큼 작고, 서버 동기화 대상이 아니므로 온디바이스 DataStore 로 충분).
 */
class UserPrefs(private val context: Context) {

    private val json = Json { ignoreUnknownKeys = true }

    val onboardingDone: Flow<Boolean> =
        context.dataStore.data.map { it[KEY_ONBOARDING] ?: false }

    val favorites: Flow<List<PlaceResult>> =
        context.dataStore.data.map { decode(it[KEY_FAVORITES]) }

    val recents: Flow<List<PlaceResult>> =
        context.dataStore.data.map { decode(it[KEY_RECENTS]) }

    suspend fun setOnboardingDone(done: Boolean) {
        context.dataStore.edit { it[KEY_ONBOARDING] = done }
    }

    suspend fun setFavorites(list: List<PlaceResult>) {
        context.dataStore.edit { it[KEY_FAVORITES] = json.encodeToString(list) }
    }

    suspend fun setRecents(list: List<PlaceResult>) {
        context.dataStore.edit { it[KEY_RECENTS] = json.encodeToString(list) }
    }

    /** 손상된/구버전 JSON 은 조용히 빈 목록으로 처리(앱이 죽지 않도록). */
    private fun decode(raw: String?): List<PlaceResult> =
        if (raw.isNullOrBlank()) emptyList()
        else runCatching { json.decodeFromString<List<PlaceResult>>(raw) }.getOrDefault(emptyList())

    private companion object {
        val KEY_ONBOARDING = booleanPreferencesKey("onboarding_done")
        val KEY_FAVORITES = stringPreferencesKey("favorites_json")
        val KEY_RECENTS = stringPreferencesKey("recents_json")
    }
}
