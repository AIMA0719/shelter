package com.shelter.shade.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.shelter.shade.data.ShadeResponse

@Composable
fun ShadeScreen(viewModel: ShadeViewModel, modifier: Modifier = Modifier) {
    val state by viewModel.state.collectAsState()

    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("그늘 경로", fontSize = 24.sp, fontWeight = FontWeight.Bold)
        Text(
            "출발·도착 좌표와 출발 시각을 정하면 경로의 그늘/햇빛을 보여줍니다.",
            style = MaterialTheme.typography.bodyMedium,
        )

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(
                value = state.originLat,
                onValueChange = viewModel::onOriginLat,
                label = { Text("출발 위도") },
                modifier = Modifier.weight(1f),
            )
            OutlinedTextField(
                value = state.originLon,
                onValueChange = viewModel::onOriginLon,
                label = { Text("출발 경도") },
                modifier = Modifier.weight(1f),
            )
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(
                value = state.destLat,
                onValueChange = viewModel::onDestLat,
                label = { Text("도착 위도") },
                modifier = Modifier.weight(1f),
            )
            OutlinedTextField(
                value = state.destLon,
                onValueChange = viewModel::onDestLon,
                label = { Text("도착 경도") },
                modifier = Modifier.weight(1f),
            )
        }

        Text("출발 시각: ${state.departHour}시")
        Slider(
            value = state.departHour.toFloat(),
            onValueChange = { viewModel.onDepartHour(it.toInt()) },
            valueRange = 0f..23f,
            steps = 22,
        )

        Button(
            onClick = viewModel::computeShade,
            modifier = Modifier.fillMaxWidth(),
            enabled = state.result !is ShadeUiResult.Loading,
        ) {
            Text("경로 그늘 보기")
        }

        when (val r = state.result) {
            is ShadeUiResult.Idle -> Unit
            is ShadeUiResult.Loading -> Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.Center,
            ) { CircularProgressIndicator() }
            is ShadeUiResult.Error -> Card(modifier = Modifier.fillMaxWidth()) {
                Text(
                    "오류: ${r.message}",
                    modifier = Modifier.padding(16.dp),
                    color = MaterialTheme.colorScheme.error,
                )
            }
            is ShadeUiResult.Success -> ResultView(r.response)
        }
    }
}

@Composable
private fun ResultView(resp: ShadeResponse) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Row(verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("그늘 ${resp.shadePercent}%", fontSize = 28.sp, fontWeight = FontWeight.Bold)
                Text("· ${resp.totalDistanceM.toInt()} m", modifier = Modifier.padding(bottom = 4.dp))
            }
            Text(
                "신뢰도 ${(resp.meanConfidence * 100).toInt()}% · 건물 ${resp.buildingCount}동 · " +
                    "샘플 ${resp.sampleCount}" + if (resp.cached) " · 캐시" else "",
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
    RouteCanvas(segments = resp.segments, modifier = Modifier.fillMaxWidth())
}
