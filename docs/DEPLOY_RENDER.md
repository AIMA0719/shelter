# 서울 전역 백엔드 — Render 무료 배포 가이드 (카드 불필요)

Render 무료 플랜에 **백엔드 + PostgreSQL(PostGIS)** 를 올린다. **신용카드 없이** 가능.
앱은 이미 "서버 우선 + 강남 온디바이스 폴백"으로 연결돼 있다.

**무료 플랜의 두 가지 특성 (관리 가능):**
- 웹 서버는 15분 유휴 시 잠듦 → 첫 요청 콜드 스타트(~30~60s). → 핑거로 완화(8단계), 앱 타임아웃 60s 로 늘려둠.
- 무료 Postgres 는 생성 **90일 후 삭제** → 새로 만들고 적재 한 번 다시(9단계). 데이터 원본은 PC 에 있으니 안 잃음.

준비물(이미 생성됨): `backend/data/seoul_all_buildings.geojson`(338MB) — 695,780개 건물.

---

## 0. 깃허브에 올리기 (Render 는 Git 저장소가 필요)

이미 로컬 git 저장소이므로 **깃허브 원격만** 연결하면 된다.
```powershell
# GitHub CLI 가 있으면 (없으면 github.com 에서 빈 repo 만들고 remote add)
gh repo create shelter --private --source . --remote origin --push
```
> ⚠️ 338MB GeoJSON 은 `.gitignore` 로 제외돼 있어 깃허브엔 안 올라간다(정상).
> 데이터는 8단계에서 **로컬 PC → Render DB** 로 직접 넣는다.

---

## 1. Render 가입
https://render.com → **Get Started** → 깃허브 계정으로 가입(카드 안 물어봄).

## 2. Blueprint 로 한 번에 생성
대시보드 → **New → Blueprint** → 0단계의 `shelter` 저장소 선택 →
Render 가 루트의 **`render.yaml`** 을 읽어 자동 구성:
- `shelter-backend` (웹 서비스, Docker)
- `shelter-db` (PostgreSQL 무료)

**Apply** 누르면 빌드 시작(Docker 빌드 ~5분).

## 3. 배포 확인
`shelter-backend` 서비스가 **Live** 가 되면 URL 이 생긴다:
```
https://shelter-backend-xxxx.onrender.com
```
이때 `/health` 는 통과하지만 `buildings_loaded` 는 아직 **0** 이다(적재 전). 정상.

## 4. DB 외부 접속 주소 복사
대시보드 → **shelter-db** → **Connections** → **External Database URL** 복사.
형식: `postgresql://user:pw@host.singapore-postgres.render.com/dbname`

## 5. 서울 전역 데이터 적재 (로컬 PC 에서 한 줄)
PC 의 저장소 폴더에서 PowerShell:
```powershell
.\deploy\render-ingest.ps1 -Dsn "위에서 복사한 External Database URL"
```
스크립트가 자동으로:
- (필요 시) `.gz` 압축 해제
- `schema.sql` 실행(PostGIS 확장 + 테이블 생성)
- 695,780개 건물 + 샘플 POI 를 **COPY** 로 적재(원격이라 수 분)

> 수동으로 하려면(backend 폴더에서):
> ```powershell
> $env:PYTHONPATH="..\shade-engine"
> python -m app.db.ingest --dsn "<External URL>?sslmode=require" `
>   --init-schema app\db\schema.sql `
>   --buildings data\seoul_all_buildings.geojson `
>   --pois data\sample_pois.geojson --replace
> ```

## 6. 적재 확인
```
https://shelter-backend-xxxx.onrender.com/health
→ {"version":"...","buildings_loaded":695780}   ← 70만 가까우면 성공
```

## 7. 앱 연결
PC 의 `app/gradle.properties` 한 줄 수정(끝에 `/` 필수, **https**):
```properties
shelter.apiBaseUrl=https://shelter-backend-xxxx.onrender.com/
```
앱 재빌드/설치하면 서울 전역이 서버에서 온다. (서버 장애 시 강남 온디바이스 폴백.)

## 8. (권장) 콜드 스타트 방지 핑거
https://uptimerobot.com (무료) → New Monitor → HTTP(s) →
URL `https://shelter-backend-xxxx.onrender.com/health`, 간격 **5분**.
→ 서버가 안 자서 첫 요청도 빠르다. (무료 가동시간 월 750h > 24h 가동 ~730h)

## 9. (90일마다) DB 재생성 시
무료 Postgres 가 만료되면:
1. Render 에서 **shelter-db** 삭제 → New → PostgreSQL(무료) 새로 생성(또는 Blueprint 재적용)
2. 새 **External Database URL** 복사
3. `.\deploy\render-ingest.ps1 -Dsn "<새 URL>"` 한 번 → 끝
4. 웹 서비스 환경변수 `SHELTER_DB_DSN` 이 새 DB 를 가리키는지 확인(Blueprint 면 자동).

---

## (선택) 기상청 실데이터
Render → shelter-backend → **Environment** → `SHELTER_KMA_SERVICE_KEY` 에 발급키 입력 → 저장(자동 재배포).
없으면 계절/시각 기반 stub 날씨로 동작.
