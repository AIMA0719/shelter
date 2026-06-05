package com.shelter.shade.data

import retrofit2.http.Body
import retrofit2.http.POST

interface ShadeApi {
    @POST("v1/shade")
    suspend fun computeShade(@Body request: ShadeRequest): ShadeResponse
}
