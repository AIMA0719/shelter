package com.shelter.shade.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/** 백엔드 /v1/shade 요청/응답 DTO. backend/app/models.py 와 1:1 대응. */

@Serializable
data class LatLng(
    val lat: Double,
    val lon: Double,
)

@Serializable
data class ShadeRequest(
    val origin: LatLng? = null,
    val destination: LatLng? = null,
    val coords: List<LatLng>? = null,
    @SerialName("depart_time") val departTime: String? = null,
    val mode: String = "walk",
    @SerialName("spacing_m") val spacingM: Double = 10.0,
    @SerialName("moving_sun") val movingSun: Boolean = true,
)

@Serializable
data class SegmentOut(
    val a: LatLng,
    val b: LatLng,
    val shaded: Boolean,
    val reason: String,
    val confidence: Double,
)

@Serializable
data class RoutesRequest(
    val origin: LatLng,
    val destination: LatLng,
    @SerialName("depart_time") val departTime: String? = null,
    val mode: String = "walk",
    @SerialName("grid_spacing_m") val gridSpacingM: Double = 20.0,
)

@Serializable
data class WeatherBadge(
    @SerialName("temp_c") val tempC: Double? = null,
    @SerialName("uv_index") val uvIndex: Double? = null,
    @SerialName("heat_advisory") val heatAdvisory: Boolean = false,
    val source: String,
)

@Serializable
data class RouteOptionOut(
    val name: String,
    @SerialName("distance_m") val distanceM: Double,
    @SerialName("shade_percent") val shadePercent: Double,
    val coords: List<LatLng>,
    val segments: List<SegmentOut>,
)

@Serializable
data class RoutesResponse(
    @SerialName("depart_time") val departTime: String,
    val mode: String,
    @SerialName("building_count") val buildingCount: Int,
    val weather: WeatherBadge? = null,
    val options: List<RouteOptionOut>,
)

@Serializable
data class ShadeResponse(
    @SerialName("shade_percent") val shadePercent: Double,
    @SerialName("total_distance_m") val totalDistanceM: Double,
    @SerialName("sample_count") val sampleCount: Int,
    @SerialName("mean_confidence") val meanConfidence: Double,
    @SerialName("depart_time") val departTime: String,
    val mode: String,
    val provider: String,
    @SerialName("building_count") val buildingCount: Int,
    val cached: Boolean = false,
    val segments: List<SegmentOut>,
)
