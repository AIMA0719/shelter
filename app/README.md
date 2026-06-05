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

## 지도 SDK — 네이버 지도 (결정됨)
지도 표시는 **네이버 지도 SDK**(`naver-map-compose`)를 쓴다. `NaverRouteMap` 이 지도 위에
경로를 그늘(초록)/햇빛(주황)으로 색칠한다. 지도 SDK 는 **표시만** 담당하고, 그늘/경로 계산은
백엔드 엔진이 한다(어떤 지도 API도 "가장 그늘진 경로"를 주지 않으므로 핵심은 우리 엔진).
`RouteCanvas`(Compose Canvas)는 키 없이 미리보기용 폴백으로 남겨 둔다.

### NCP 키 설정 (필수)
1. [NAVER Cloud Platform](https://www.ncloud.com) → Maps → Application 등록 → *Mobile Dynamic Map* 활성화.
2. 발급된 **NCP 키 ID** 를 `app/local.properties` 에 넣는다(저장소에 커밋되지 않음):
   ```properties
   NCP_KEY_ID=발급받은_키
   ```
3. 빌드 시 `build.gradle` 이 이를 읽어 `AndroidManifest` 의
   `com.naver.maps.map.NCP_KEY_ID` meta-data 로 주입한다. 키가 없으면 지도에 인증
   오류가 표시되지만 빌드/컴파일은 정상이다.

> 참고: 네이버 Directions API 는 자동차 경로 위주라 도보 경로 데이터엔 한계가 있다.
> 실제 보행 경로 그래프는 OSM 도보 네트워크(또는 Tmap 보행자 API)로 확장한다.

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
