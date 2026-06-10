package com.shelter.shade.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Map
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector

/**
 * 앱 최상위 컴포저블 — 온보딩 게이트 + 하단 네비게이션(지도/설정).
 *
 * 온보딩 완료 여부는 DataStore 에서 비동기 로드되므로 로딩 중(null)에는 빈 배경만 그려
 * '온보딩→지도' 가 깜빡이며 번갈아 보이는 것을 막는다.
 */
@Composable
fun ShelterApp(viewModel: ShadeViewModel) {
    val state by viewModel.state.collectAsState()
    when (state.onboardingComplete) {
        null -> Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {}
        false -> OnboardingScreen(onDone = { viewModel.completeOnboarding() })
        true -> MainScaffold(viewModel)
    }
}

private enum class Tab(val label: String, val icon: ImageVector) {
    MAP("지도", Icons.Filled.Map),
    SETTINGS("설정", Icons.Filled.Settings),
}

@Composable
private fun MainScaffold(viewModel: ShadeViewModel) {
    val tabs = Tab.entries
    var selected by rememberSaveable { mutableIntStateOf(0) }

    Column(Modifier.fillMaxSize()) {
        // 지도는 항상 컴포지션에 남겨 두고(무거운 NaverMap MapView 재생성 방지) 설정은 그 위에
        // 불투명 오버레이로 띄운다. 탭 전환 시에도 경로 계산 결과·카메라 상태가 유지된다.
        Box(Modifier.weight(1f).fillMaxWidth()) {
            MapScreen(viewModel = viewModel)
            if (tabs[selected] == Tab.SETTINGS) {
                SettingsScreen(viewModel = viewModel)
            }
        }
        NavigationBar {
            tabs.forEachIndexed { index, tab ->
                NavigationBarItem(
                    selected = selected == index,
                    onClick = { selected = index },
                    icon = { Icon(tab.icon, contentDescription = tab.label) },
                    label = { Text(tab.label) },
                )
            }
        }
    }
}
