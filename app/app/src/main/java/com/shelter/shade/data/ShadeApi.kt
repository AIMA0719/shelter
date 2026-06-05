package com.shelter.shade.data

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Query

interface ShadeApi {
    @POST("v1/shade")
    suspend fun computeShade(@Body request: ShadeRequest): ShadeResponse

    @POST("v1/routes")
    suspend fun planRoutes(@Body request: RoutesRequest): RoutesResponse

    @POST("v1/departure-suggest")
    suspend fun suggestDeparture(@Body request: DepartureSuggestRequest): DepartureSuggestResponse

    @GET("v1/pois")
    suspend fun getPois(
        @Query("min_lat") minLat: Double,
        @Query("min_lon") minLon: Double,
        @Query("max_lat") maxLat: Double,
        @Query("max_lon") maxLon: Double,
    ): PoisResponse
}
