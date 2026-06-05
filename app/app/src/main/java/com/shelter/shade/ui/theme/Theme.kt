package com.shelter.shade.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// 그늘 = 초록, 햇빛 = 주황 (지도 색칠과 동일한 언어)
val ShadeGreen = Color(0xFF2E7D32)
val SunOrange = Color(0xFFF9A825)
private val Primary = Color(0xFF00695C)

private val LightColors = lightColorScheme(primary = Primary)
private val DarkColors = darkColorScheme(primary = Color(0xFF4DB6AC))

@Composable
fun ShelterTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        content = content,
    )
}
