# backend — Shelter Shade API (Phase 1 MVP)

FastAPI 백엔드. 경로(출발/도착 또는 명시 좌표)와 출발 시각을 받아 `shade_engine` 으로
구간별 그늘/햇빛을 판정하고 그늘 % 를 반환한다.

## 엔드포인트
| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/health` | 상태 + 적재된 건물 수 |
| POST | `/v1/shade` | 경로 그늘 판정 |

### POST /v1/shade 예시
```json
{
  "origin": {"lat": 37.49750, "lon": 127.02700},
  "destination": {"lat": 37.49900, "lon": 127.02700},
  "depart_time": "2026-07-15T16:00:00+09:00",
  "mode": "walk"
}
```
`coords`(2점 이상)를 주면 directions 탐색을 생략하고 그 경로를 그대로 쓴다.

## 구조
```
app/
├─ main.py            # FastAPI 앱, 라우트
├─ models.py          # pydantic 요청/응답
├─ shade_service.py   # 경로 획득 → shade_engine → 응답 + 캐싱
├─ directions.py      # 경로 제공자(straight/kakao)
├─ buildings_repo.py  # 건물 소스(GeoJSON / 메모리; 추후 PostGIS)
├─ cache.py           # 경로 단위 LRU 캐시
└─ config.py          # 환경변수 설정
data/sample_buildings.geojson  # 강남 합성 건물(데모/테스트)
```

## 설정(환경변수)
| 변수 | 기본 | 설명 |
|---|---|---|
| `SHELTER_BUILDINGS_GEOJSON` | `data/sample_buildings.geojson` | 건물 데이터 |
| `SHELTER_DIRECTIONS_PROVIDER` | `straight` | `straight`(오프라인) / `kakao` |
| `SHELTER_KAKAO_REST_API_KEY` | – | 카카오 길찾기 키 |
| `SHELTER_BBOX_MARGIN_M` | `300` | 건물 조회 bbox 확장(그림자 도달) |

> 카카오/네이버 directions 의 상업적 이용·그림자 오버레이 허용 여부는 DEV_PLAN §8
> 약관 검토 후 운영 적용한다. 기본 제공자 `straight` 는 검증/오프라인용.

## 실행
```bash
cd backend
python -m pip install -r requirements.txt
# shade_engine(형제 패키지)을 경로에 추가해 실행
PYTHONPATH=../shade-engine uvicorn app.main:app --reload --port 8000
```

## 테스트
```bash
cd backend
pytest    # pythonpath 는 pyproject.toml 에 설정됨
```
