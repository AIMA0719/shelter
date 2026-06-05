package com.shelter.shade.data

/** API 호출을 감싸는 저장소. ViewModel 은 이 추상화에만 의존한다. */
class ShadeRepository(private val api: ShadeApi = NetworkModule.shadeApi) {

    suspend fun fetchRouteShade(
        origin: LatLng,
        destination: LatLng,
        departTimeIso: String,
        mode: String = "walk",
    ): ShadeResponse =
        api.computeShade(
            ShadeRequest(
                origin = origin,
                destination = destination,
                departTime = departTimeIso,
                mode = mode,
            )
        )

    suspend fun fetchRouteOptions(
        origin: LatLng,
        destination: LatLng,
        departTimeIso: String,
        mode: String = "walk",
    ): RoutesResponse =
        api.planRoutes(
            RoutesRequest(
                origin = origin,
                destination = destination,
                departTime = departTimeIso,
                mode = mode,
            )
        )
}
