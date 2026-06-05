# shade-engine — Shelter 그늘 엔진 (Phase 0)

태양 위치 + 건물 높이로 경로의 각 지점이 **그늘인지 햇빛인지** 판정하는 코어 엔진.
DEV_PLAN.md 의 Phase 0(타당성 프로토타입) 산출물이며, Phase 1 백엔드가 이 모듈에 의존한다.

## 설계 원칙
- **코어는 표준 라이브러리만** 사용 → 어디서든 설치 없이 `import` · 테스트 가능.
- 그림자 = 태양의 기하(방위각·고도각)와 건물 높이의 관계. 지면 관측자·평지붕 1차 근사.
- 좌표는 좁은 영역용 로컬 ENU(미터) 평면에서 처리.

## 구조
| 모듈 | 역할 |
|---|---|
| `geo.py` | 위경도 ↔ 로컬 미터 평면, 거리/방위 |
| `sun.py` | NOAA 알고리즘 태양 위치(방위각/고도각) |
| `buildings.py` | 건물 모델 + 높이 추정(height > levels×3m > 기본 9m) |
| `raycast.py` | **레이캐스팅 그늘 판정**(엔진의 심장) |
| `engine.py` | 경로 샘플링 → 구간별 판정 → 그늘% 집계(이동 중 태양 이동 반영) |
| `overpass.py` | (선택) OSM 건물 추출 — urllib |
| `viz.py` | (선택) Leaflet HTML 시각화 — 의존성 없음 |
| `demo.py` | 합성 데이터 오프라인 데모 |

## 빠른 시작
```bash
cd shade-engine
python -m shade_engine.demo                 # 아침/정오/오후 그늘% 비교
python -m shade_engine.demo --html out.html # 오후 케이스 지도 저장 후 브라우저로 열기
```

## 테스트
```bash
cd shade-engine
python -m pip install -e ".[dev]"   # 또는: pip install pytest
pytest
```

## 그늘 판정 원리 (raycast)
한 지점에서 태양 방위각 방향으로 광선을 쏜다. 수평 거리 `d` 에서 태양 광선의 높이는
`d × tan(고도각)`. 그 거리의 건물 높이가 이 값 이상이면 태양을 가리므로 **그늘**.
태양이 지평선 근처(고도 ≤ 0.5°)면 직사광선이 없다고 보고 그늘로 처리한다.
건물 높이가 추정값이고 임계 높이에 근접하면 신뢰도를 낮춘다.

## 한계 (Phase 1+ 개선 대상)
- 가로수·지형(DEM) 미반영 → Phase 2 에서 캐스터 추가.
- 평지붕·수직벽 가정(경사 지붕 무시).
- 로컬 평면 근사 → 매우 긴 경로에는 부적합(권역 단위 OK).
