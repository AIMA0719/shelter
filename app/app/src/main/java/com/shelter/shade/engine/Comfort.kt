package com.shelter.shade.engine

/** 체감 쾌적도 점수(0~100). 그늘이 많을수록·덜 더울수록·자외선이 약할수록 높다. */
object Comfort {
    private const val BASE_SUN_PENALTY = 10.0
    private const val NEUTRAL_TEMP_C = 22.0

    fun score(shadeFraction: Double, tempC: Double?, uvIndex: Double?): Double {
        val shade = shadeFraction.coerceIn(0.0, 1.0)
        val sun = 1.0 - shade
        val heatExcess = if (tempC == null) 0.0 else maxOf(0.0, tempC - NEUTRAL_TEMP_C)
        val uv = uvIndex ?: 0.0
        val penalty = sun * (BASE_SUN_PENALTY + heatExcess * 2.0 + uv * 3.0)
        return ((100.0 - penalty).coerceAtLeast(0.0) * 10).toInt() / 10.0
    }
}
