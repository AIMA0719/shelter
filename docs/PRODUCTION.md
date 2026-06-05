# 서울 전역 실서비스 체크리스트

PRD/DEV_PLAN 의 MVP 를 **서울 전역 실서비스**로 올리기 위해 필요한 것들. 코드로 적용
가능한 부분은 이번에 반영했고(A), 데이터·인프라처럼 코드 밖 작업은 항목으로 정리한다(B~D).

---

## A. 코드로 이미 개선한 것 (이번 변경)

### 성능 — 공간 인덱스 (서울 전역 핵심)
선형 O(n) 스캔이던 핫패스를 모두 그리드 공간 인덱스로 교체.

| 대상 | 이전 | 이후 |
|---|---|---|
| 건물 그늘 레이캐스팅(`raycast.BuildingIndex`) | 샘플마다 전체 건물 스캔 | 반경 내 셀의 건물만 |
| 건물 저장소 bbox 질의(`buildings_repo`) | 전체 건물 스캔 | 겹치는 셀만 |
| OSM 최근접 노드(`OsmGraph.nearest_node`) | 전체 노드 스캔 | 그리드 + 확장 링(종료 보장) |

벤치(개발 PC): 건물 5,041개·142샘플 경로 **52.7ms**, `nearest_node` **0.012ms/호출**.
인덱스가 무차별 탐색과 **동일 결과**임을 테스트로 검증(`test_building_index`,
`test_nearest_node_index_matches_bruteforce`).

### 견고성
- **스레드 안전 LRU 캐시** — FastAPI 동기 핸들러는 스레드풀에서 동시 실행되므로 락 보호.
- **`/v1/routes` 캐싱** — 라우팅+그늘 계산이 무거워 재요청 시 재계산 방지(`cached` 플래그).
- **입력 가드** — `/v1/shade` 경로 ≤ 50km·좌표 ≤ 5000, `/v1/routes`·`departure-suggest`
  직선거리 ≤ 30km. 폭주/오용 시 422.
- **레이트리밋** — IP 당 분당 요청 한도(`SHELTER_RATE_LIMIT_PER_MIN`, 기본 600) → 429.
- **OSM 라우팅 폴백** — 보행망 범위 밖/단절이면 격자로 폴백(잘못된 0거리·점프 경로 방지).

### 데이터/인프라 경로 (코드로 자동화 완료, 실행은 키/네트워크 필요)
- **무료 OSM 데이터 부트스트랩** — `shade-engine/scripts/fetch_district.py --name gangnam
  --bbox ...` 한 줄로 권역 **건물(높이 태그)+보행망**을 받아 백엔드 데이터로 저장. V-World
  같은 유료 데이터 없이 MVP/권역 단위 가능.
- **PostGIS 저장소** — `app/db/`(schema.sql · postgis_repo.py · ingest.py). `SHELTER_DB_DSN`
  지정 시 건물/POI 를 GeoJSON 대신 PostGIS(GiST)에서 조회(서울 전역). 인터페이스 동일.
- **기상청(KMA) 클라이언트** — `SHELTER_KMA_SERVICE_KEY` 지정 시 실데이터, 없으면 stub.
- **배포** — `backend/Dockerfile`, `docker-compose.yml`(backend+PostGIS), `.env.example`,
  GitHub Actions CI(`.github/workflows/ci.yml`, 두 패키지 테스트).

---

## B. 데이터 (코드 밖 · 필수)

| 항목 | 현재 | 운영 필요 |
|---|---|---|
| **건물 높이** | 샘플 + `fetch_district.py`(무료 OSM) | 권역은 OSM 으로 즉시 가능. 서울 전역·고정밀은 V-World 건물통합정보/NSDI 로 보강 → PostGIS 적재 |
| **보행 네트워크** | 샘플 + `fetch_district.py`/`fetch_walk_network.py`(무료 OSM) | 권역/전역 OSM 보행망 정기 동기화 |
| **가로수** | 합성 | 서울시 가로수 현황 오픈데이터(위치·수고·수관폭) |
| **쉼터 POI** | 샘플 4개 | 지자체 무더위쉼터·그늘막·음수대 오픈데이터 |
| **기상** | stub(계절/시각 추정) | 기상청 API 키(자외선·기온·폭염특보) |
| **지도** | 네이버 SDK 연동 | NCP 키 발급 + 그림자 오버레이 약관 확인 |

> 건물 데이터 품질이 그늘 정확도를 좌우한다. 높이 누락률·오차를 측정하고 신뢰도
> (`ShadeResult.confidence`)에 반영하는 정책을 운영 전 확정.

## C. 인프라 / 운영

- **DB**: PostGIS(건물·POI·그래프, GiST 공간 인덱스). 현재 인메모리/파일 → 동일 인터페이스
  (`BuildingsRepository`)라 저장소 클래스만 교체하면 됨.
- **그늘 래스터 사전계산 + 타일 캐시**(시각×날짜버킷): 대량 트래픽 시 요청당 계산 대신 샘플링.
- **라우팅 확장**: 자체 그래프 → **Valhalla/OSRM**(전역 그래프·고속 탐색). 가중치 공식
  (거리×(1+α·햇빛))은 그대로 커스텀 코스팅으로 이식.
- **공간 인덱스 영속화**: 현재는 요청/적재 시 인메모리 구축. 전역 규모면 사전 구축·캐시.
- 비동기 워커, 레이트리밋, 모니터링, 헬스체크(`/health` 존재), 배포 파이프라인.

## D. 알고리즘 정확도 (후순위)

- 건물 **구멍(inner ring)** 무시 → 약간의 과대 그늘. 경사 지붕·DEM(지형) 미반영.
- 가로수 **투과율**(잎 밀도/계절) 미반영 — 현재 불투명 가정.
- 로컬 평면(등거리원통) 근사 — 권역 단위는 OK, 매우 긴 경로엔 적절 투영 필요.
- `nearest_node` 그리드는 권역(수만 노드)까진 빠름. 서울 전역(수십만+)·고QPS 면
  R-tree/Valhalla 권장.
