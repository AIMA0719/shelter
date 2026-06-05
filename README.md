# Shelter (가칭 「그늘로」) 🌳

출발지–목적지 경로에서 **어디가 그늘이고 어디가 햇빛인지** 알려주고, 같은 목적지라도
**가장 그늘진 길**을 추천하는 도보·자전거용 경로 안내 앱.

> "지도 앱은 *어디에 뭐가 있는지*는 알려주지만, *이 길을 걸으면 얼마나 땡볕인지*는 안 알려준다."

- 기획: [docs/PRD.md](docs/PRD.md) · 개발 계획: [docs/DEV_PLAN.md](docs/DEV_PLAN.md)

## 모노레포 구성

| 디렉터리 | 내용 | 상태 |
|---|---|---|
| [`shade-engine/`](shade-engine/) | 그늘 엔진(태양위치 NOAA + 건물/가로수 레이캐스팅 + 그늘 가중 라우팅) | 테스트 41개 ✅ |
| [`backend/`](backend/) | FastAPI 그늘 판정·경로추천·출발시간추천·POI API | 테스트 30개 ✅ |
| [`app/`](app/) | Kotlin/Compose 안드로이드 앱 (네이버 지도 SDK) | `assembleDebug` 빌드 성공 ✅ |

## 핵심 원리

그늘 = **태양의 기하**(방위각·고도각)와 **빛을 가리는 물체**(건물·가로수)의 관계.
한 지점에서 태양 방향으로 광선을 쏴, 거리 `d` 에서 건물 높이가 `d×tan(고도각)` 이상이면 그늘.
그늘 가중 라우팅은 격자 그래프에서 **엣지비용 = 거리×(1+α·햇빛비율)** 의 다익스트라
(Valhalla 커스텀 코스팅과 동일 원리; α↑ = 더 그늘진 길).

## 페이즈별 구현

- **Phase 0** — 그늘 엔진 타당성(순수 파이썬 코어, 합성 데이터 데모/검증)
- **Phase 1** — MVP: 단일 경로 그늘 색칠 + 그늘% (백엔드 + 안드로이드)
- **Phase 2** — 그늘 가중 라우팅(최단/균형/그늘) + 자전거 + 가로수 + 기상 배지
- **Phase 3** — 출발 시간 추천 + 쾌적도 점수 + 쉼터 POI + 겨울 햇빛 모드

각 페이즈는 코덱스(OpenAI) 독립 리뷰를 거쳐 발견 사항을 수정·회귀 테스트화했다.

## 빌드 & 테스트

```bash
# 그늘 엔진
cd shade-engine && python -m pip install -e ".[dev]" && pytest
python -m shade_engine.demo            # 아침/정오/오후 그늘% 데모

# 백엔드
cd backend && python -m pip install -r requirements.txt
PYTHONPATH=../shade-engine uvicorn app.main:app --port 8000
pytest

# 안드로이드 (Android Studio 로 열거나)
cd app && ./gradlew :app:assembleDebug :app:testDebugUnitTest
```

## API 요약 (backend)

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/health` | 상태 + 적재 건물 수 |
| POST | `/v1/shade` | 단일 경로 그늘 판정 |
| POST | `/v1/routes` | 최단/균형/그늘 경로 비교 + 쾌적도 + 기상 |
| POST | `/v1/departure-suggest` | 출발 시간 추천(여름 그늘/겨울 햇빛) |
| GET | `/v1/pois` | 그늘막·쿨링쉼터·음수대 POI |

## 한계 / 다음 단계 (운영 전)

- 지도 SDK 는 **네이버 지도**로 결정·연동 완료 — 운영 전 NCP 키 발급 + 그림자 오버레이
  약관 최종 확인 필요([app/README](app/README.md) 참고).
- 건물 데이터는 OSM/샘플 — 서울 전역은 V-World 등으로 정제·PostGIS 적재 필요.
- 라우팅은 격자 프로토타입 — 운영은 OSM 도로 그래프 + Valhalla 로 대체(공식 동일).
  네이버 Directions 는 자동차 위주라 도보 경로는 OSM/Tmap 보행자로 확장.
- 기상은 stub — 기상청 API 연동 필요.
