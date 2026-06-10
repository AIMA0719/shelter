package com.shelter.shade.ui

import android.Manifest
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.DirectionsWalk
import androidx.compose.material.icons.filled.AccessTime
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Park
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.shelter.shade.data.LocationProvider
import com.shelter.shade.ui.theme.ShadeGreen

/**
 * 첫 실행 온보딩 — 앱이 무엇을 하는지 짧게 소개하고, 위치 권한을 '왜 필요한지' 설명한 뒤
 * 사용자 동의 하에 요청한다(Android 권장: 권한 요청 전 rationale 제시). 권한은 선택사항이며
 * 거부해도 검색·지도 길게누르기로 이용할 수 있음을 명시한다.
 */
@Composable
fun OnboardingScreen(onDone: () -> Unit) {
    val context = LocalContext.current
    var granted by remember { mutableStateOf(LocationProvider.hasPermission(context)) }
    val permLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions(),
    ) { result -> granted = result.values.any { it } }

    Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(
            Modifier.fillMaxSize().systemBarsPadding().padding(24.dp).verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Spacer(Modifier.size(8.dp))
            Text("그늘로", style = MaterialTheme.typography.displaySmall, fontWeight = FontWeight.Bold, color = ShadeGreen)
            Text(
                "햇빛을 피해 가장 그늘진 길로 안내하는 보행·자전거 길찾기",
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            Spacer(Modifier.size(8.dp))
            Feature(Icons.Filled.Park, "그늘이 많은 경로", "건물·가로수 그림자를 계산해 가장 시원한 길을 추천해요.")
            Feature(Icons.Filled.AccessTime, "시간대별 그늘", "출발 시각을 바꿔 가며 그늘이 가장 많은 때를 찾아줘요.")
            Feature(Icons.AutoMirrored.Filled.DirectionsWalk, "도보·자전거", "겨울엔 반대로 '햇빛 좋은 길' 모드도 있어요.")

            Spacer(Modifier.size(8.dp))
            Card(
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
                shape = RoundedCornerShape(14.dp),
            ) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("위치 권한 (선택)", fontWeight = FontWeight.Bold)
                    Text(
                        "현재 위치를 출발지로 자동 지정하는 데만 사용해요. 경로를 계산할 때 출발·도착 좌표가 " +
                            "서버로 전송돼요. 권한 없이도 장소 검색이나 지도 길게 누르기로 이용할 수 있어요.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    if (granted) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            Icon(Icons.Filled.CheckCircle, contentDescription = null, tint = ShadeGreen, modifier = Modifier.size(20.dp))
                            Text("위치 권한이 허용됐어요", color = ShadeGreen, style = MaterialTheme.typography.bodyMedium)
                        }
                    } else {
                        OutlinedButton(
                            onClick = {
                                permLauncher.launch(
                                    arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION),
                                )
                            },
                            modifier = Modifier.fillMaxWidth(),
                        ) { Text("위치 권한 허용") }
                    }
                }
            }

            Spacer(Modifier.size(4.dp))
            Button(onClick = onDone, modifier = Modifier.fillMaxWidth()) {
                Text(if (granted) "시작하기" else "권한 없이 시작하기")
            }
        }
    }
}

@Composable
private fun Feature(icon: ImageVector, title: String, body: String) {
    Row(horizontalArrangement = Arrangement.spacedBy(14.dp), verticalAlignment = Alignment.Top) {
        Icon(icon, contentDescription = null, tint = ShadeGreen, modifier = Modifier.size(28.dp).padding(top = 2.dp))
        Column(Modifier.fillMaxWidth()) {
            Text(title, fontWeight = FontWeight.Bold)
            Text(body, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}
