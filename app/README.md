# app — Shelter Android (Phase 1 MVP)

Kotlin + Jetpack Compose 안드로이드 앱. 백엔드 `/v1/shade` 를 호출해 경로의 그늘/햇빛을
시각화한다.

## 화면 흐름
출발/도착 좌표 입력 → 출발 시각 슬라이더(0~23시) → **경로 그늘 보기** →
그늘 % 배지 + 거리/신뢰도/건물수 + **그늘 색칠 경로**(초록=그늘, 주황=햇빛).

## 구조
```
app/src/main/java/com/shelter/shade/
├─ MainActivity.kt              # Compose 진입점
├─ data/                        # Retrofit API, DTO, 저장소, 네트워크 설정
│  ├─ ApiModels.kt  ShadeApi.kt  NetworkModule.kt  ShadeRepository.kt
├─ ui/
│  ├─ ShadeViewModel.kt         # 상태/요청 (StateFlow)
│  ├─ ShadeScreen.kt            # 입력·시각 슬라이더·결과
│  ├─ RouteCanvas.kt            # 지도 SDK 결정 전 자립형 경로 색칠(Canvas)
│  └─ theme/Theme.kt
└─ util/GeoFormat.kt            # 순수 좌표 파싱(JVM 테스트 대상)
```

## 지도 SDK
DEV_PLAN 기준 지도 SDK 는 **Phase 0 말 결정(미정)**. 그 전까지는 외부 키 없이
컴파일·실행되도록 `RouteCanvas`(Compose Canvas)로 경로를 그린다. 네이버/카카오/MapLibre
확정 후 이 컴포저블을 실제 지도 오버레이로 교체한다.

## 백엔드 주소
`gradle.properties` 의 `shelter.apiBaseUrl` → `BuildConfig.API_BASE_URL`.
에뮬레이터에서 호스트 PC 백엔드는 `http://10.0.2.2:8000/`.

## 빌드
```bash
cd app
# 최초 1회 래퍼 생성(또는 Android Studio 가 자동 생성)
gradle wrapper --gradle-version 8.9
./gradlew :app:testDebugUnitTest   # JVM 단위 테스트
./gradlew :app:assembleDebug       # APK
```
> 이 저장소에는 `gradle-wrapper.jar`(바이너리)가 포함되어 있지 않다. Android Studio 로
> 열거나 위 `gradle wrapper` 명령으로 생성할 것.
