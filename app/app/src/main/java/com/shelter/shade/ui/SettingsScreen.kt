package com.shelter.shade.ui

import android.content.Intent
import android.net.Uri
import android.provider.Settings
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.OpenInNew
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Star
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.collectAsState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.shelter.shade.BuildConfig
import com.shelter.shade.ui.theme.SunOrange

/**
 * 설정 탭 — 위치 권한 바로가기, 온보딩 다시 보기, 즐겨찾기 관리, 그리고 데이터 출처/라이선스 표기.
 *
 * 출처 표기는 ODbL(OpenStreetMap) 의무사항이기도 하다: 길찾기 도로망·장소 검색이 OSM 파생
 * 데이터를 쓰므로 "© OpenStreetMap contributors, ODbL" 를 명시하고 라이선스 링크를 제공한다.
 */
@Composable
fun SettingsScreen(viewModel: ShadeViewModel) {
    val state by viewModel.state.collectAsState()
    val context = LocalContext.current

    fun openUrl(url: String) = runCatching {
        context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
    }
    fun openAppSettings() = runCatching {
        context.startActivity(
            Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.fromParts("package", context.packageName, null)),
        )
    }

    Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(
            Modifier.fillMaxSize().statusBarsPadding().verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Text("설정", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
            Spacer(Modifier.size(8.dp))

            SectionTitle("일반")
            SettingRow(
                icon = Icons.Filled.LocationOn,
                title = "위치 권한",
                subtitle = "시스템 설정에서 권한을 변경해요",
                onClick = { openAppSettings() },
            )
            SettingRow(
                icon = Icons.Filled.Refresh,
                title = "온보딩 다시 보기",
                subtitle = "앱 소개와 위치 권한 안내를 다시 봐요",
                onClick = { viewModel.resetOnboarding() },
            )

            Spacer(Modifier.size(8.dp))
            SectionTitle("즐겨찾기")
            if (state.favorites.isEmpty()) {
                Text(
                    "아직 즐겨찾기가 없어요. 검색 결과 옆의 ☆를 눌러 담아 보세요.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.outline,
                    modifier = Modifier.padding(vertical = 8.dp, horizontal = 4.dp),
                )
            } else {
                state.favorites.forEach { fav ->
                    Row(Modifier.fillMaxWidth().padding(vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text(fav.name, fontWeight = FontWeight.Bold, maxLines = 1)
                            fav.address?.let {
                                Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.outline, maxLines = 1)
                            }
                        }
                        IconButton(onClick = { viewModel.toggleFavorite(fav) }) {
                            Icon(Icons.Filled.Star, contentDescription = "즐겨찾기 해제", tint = SunOrange)
                        }
                    }
                    HorizontalDivider()
                }
            }

            Spacer(Modifier.size(8.dp))
            SectionTitle("데이터 출처 및 라이선스")
            LinkRow(
                title = "지도 표시",
                subtitle = "© NAVER — 네이버 지도",
                onClick = { openUrl("https://www.ncloud.com/product/applicationService/maps") },
            )
            LinkRow(
                title = "도로망·길찾기",
                subtitle = "© OpenStreetMap contributors · ODbL",
                onClick = { openUrl("https://www.openstreetmap.org/copyright") },
            )
            LinkRow(
                title = "장소 검색(지오코딩)",
                subtitle = "OSM Nominatim · ODbL",
                onClick = { openUrl("https://nominatim.org/") },
            )
            LinkRow(
                title = "건물 형상·높이",
                subtitle = "OpenStreetMap(ODbL) 및 국토교통부 V-World 기반 추정",
                onClick = { openUrl("https://www.vworld.kr/") },
            )
            LinkRow(
                title = "날씨·자외선",
                subtitle = "기상청(KMA) 공공데이터",
                onClick = { openUrl("https://www.data.go.kr/") },
            )
            LinkRow(
                title = "ODbL 라이선스 전문",
                subtitle = "Open Database License v1.0",
                onClick = { openUrl("https://opendatacommons.org/licenses/odbl/1-0/") },
            )

            Spacer(Modifier.size(8.dp))
            SectionTitle("정보")
            Text(
                "그늘로 v${BuildConfig.VERSION_NAME}",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.outline,
                modifier = Modifier.padding(vertical = 8.dp, horizontal = 4.dp),
            )
        }
    }
}

@Composable
private fun SectionTitle(text: String) {
    Text(
        text,
        style = MaterialTheme.typography.titleSmall,
        fontWeight = FontWeight.Bold,
        color = MaterialTheme.colorScheme.primary,
        modifier = Modifier.padding(top = 8.dp, bottom = 4.dp, start = 4.dp),
    )
}

@Composable
private fun SettingRow(icon: ImageVector, title: String, subtitle: String, onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().clickable(onClick = onClick).padding(vertical = 12.dp, horizontal = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Icon(icon, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
        Column(Modifier.weight(1f)) {
            Text(title, fontWeight = FontWeight.Bold)
            Text(subtitle, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.outline)
        }
    }
    HorizontalDivider()
}

@Composable
private fun LinkRow(title: String, subtitle: String, onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().clickable(onClick = onClick).padding(vertical = 12.dp, horizontal = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Column(Modifier.weight(1f)) {
            Text(title, fontWeight = FontWeight.Bold)
            Text(subtitle, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.outline)
        }
        Icon(
            Icons.AutoMirrored.Filled.OpenInNew,
            contentDescription = "열기",
            tint = MaterialTheme.colorScheme.outline,
            modifier = Modifier.size(18.dp),
        )
    }
    HorizontalDivider()
}
