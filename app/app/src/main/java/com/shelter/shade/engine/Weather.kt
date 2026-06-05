package com.shelter.shade.engine

/** 온디바이스 날씨 추정(stub). 네트워크/키 없이 계절·시각으로 근사. */
data class WeatherInfo(val tempC: Double?, val uvIndex: Double?, val heatAdvisory: Boolean, val source: String = "stub")

object Weather {
    /** monthKst: 1~12, hourKst: 0~23 */
    fun badge(monthKst: Int, hourKst: Int): WeatherInfo {
        val isSummer = monthKst in 6..8
        val midday = maxOf(0.0, 1.0 - kotlin.math.abs(hourKst - 14) / 9.0)
        val temp: Double
        val uv: Double
        if (isSummer) {
            temp = 26.0 + 9.0 * midday
            uv = ((2.0 + 9.0 * midday) * 10).toInt() / 10.0
        } else {
            temp = 8.0 + 10.0 * midday
            uv = ((1.0 + 4.0 * midday) * 10).toInt() / 10.0
        }
        val t = (temp * 10).toInt() / 10.0
        return WeatherInfo(tempC = t, uvIndex = uv, heatAdvisory = t >= 33.0)
    }
}
