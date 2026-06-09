package com.shelter.shade.data

import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory
import com.shelter.shade.BuildConfig
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import java.util.concurrent.TimeUnit

/** Retrofit + kotlinx.serialization 네트워크 설정(간단 수동 DI). */
object NetworkModule {

    private val json = Json {
        ignoreUnknownKeys = true
        explicitNulls = false
    }

    private val client: OkHttpClient by lazy {
        OkHttpClient.Builder()
            .addInterceptor(HttpLoggingInterceptor().apply {
                level = if (BuildConfig.DEBUG) {
                    HttpLoggingInterceptor.Level.BODY
                } else {
                    HttpLoggingInterceptor.Level.NONE
                }
            })
            // Render 무료 플랜은 유휴 시 잠들어, 첫 요청에서 컨테이너가 깨어나는 데
            // ~30~60초가 걸릴 수 있다(콜드 스타트). 그 한 번을 견디도록 넉넉히.
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(60, TimeUnit.SECONDS)
            .callTimeout(75, TimeUnit.SECONDS)
            .build()
    }

    val shadeApi: ShadeApi by lazy {
        Retrofit.Builder()
            .baseUrl(BuildConfig.API_BASE_URL)
            .client(client)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
            .create(ShadeApi::class.java)
    }
}
