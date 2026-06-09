# 서울 전역 백엔드 — Oracle Cloud 무료 VM 배포 가이드

이 백엔드는 **PostGIS(공간 DB)** 가 필요해서 Firebase 순정(Functions+Firestore)으론
못 올린다. 대신 **Oracle Cloud Always Free ARM VM** 에 Docker 스택(PostGIS + 백엔드)을
통째로 올리면 **서울 전역 70만 동을 영구 무료**로 서비스할 수 있다.

> 앱은 이미 "서버 우선 + 강남 온디바이스 폴백"으로 연결돼 있다. 서버가 살아 있으면
> 서울 전역, 죽어 있으면 강남만 오프라인 동작한다.

준비물: 변환된 데이터(이미 생성됨)
- `backend/data/seoul_all_buildings.geojson` (338MB) — 또는 압축본 `.gz` (84MB)

---

## 1. Oracle 무료 계정 + VM 만들기 (웹 콘솔, ~15분)

1. https://www.oracle.com/cloud/free 가입 (카드 인증 필요하지만 **Always Free 리소스는 과금 안 됨**).
2. 콘솔 → **Compute → Instances → Create instance**
   - Image: **Ubuntu 22.04**
   - Shape: **Ampere (VM.Standard.A1.Flex)** 선택 → **OCPU 2, 메모리 12GB** 권장
     (Always Free 한도: ARM 4 OCPU / 24GB 까지 무료. PostGIS+70만 동엔 넉넉)
   - **SSH 키**: 키쌍 생성 후 개인키(.key) 다운로드 — 접속에 쓴다.
   - Create.
3. 인스턴스 상세에서 **Public IP** 를 적어둔다. (이하 `VM_IP`)

### 1-1. 포트 8000 열기 (이거 안 하면 외부에서 접속 불가)

콘솔 → 인스턴스의 **VCN → Security Lists → Default Security List → Add Ingress Rules**
- Stateless: 체크 해제
- Source CIDR: `0.0.0.0/0`
- IP Protocol: `TCP`
- Destination Port Range: `8000`
- Add.

(호스트 내부 iptables 는 아래 셋업 스크립트가 자동으로 연다.)

---

## 2. VM 접속

```bash
# 다운받은 키 권한 조정 후 접속 (Windows 는 PowerShell/Git Bash)
chmod 400 ssh-key.key
ssh -i ssh-key.key ubuntu@VM_IP
```

---

## 3. 코드 + 데이터 올리기

VM 안에서:
```bash
git clone <이-저장소-URL> shelter
cd shelter
```

로컬 PC 에서 (다른 터미널) 압축 데이터를 VM 으로 전송:
```bash
# 84MB — 몇 분이면 됨
scp -i ssh-key.key \
  backend/data/seoul_all_buildings.geojson.gz \
  ubuntu@VM_IP:~/shelter/backend/data/
```

> `.gz` 만 올리면 셋업 스크립트가 알아서 압축을 푼다.

---

## 4. 한 줄 배포

VM 안에서:
```bash
bash deploy/oracle-setup.sh
```

스크립트가 자동으로:
1. Docker + compose 설치
2. 호스트 방화벽 8000 개방
3. `.gz` 압축 해제
4. `docker compose up -d --build` (PostGIS + 백엔드)
5. **서울 전역 건물 PostGIS 적재**(`ingest --replace`, COPY 라 수십 초)
6. 헬스체크 + 외부 접속 주소 출력

끝나면 이런 게 뜬다:
```
✅ 완료. 외부 접속 주소:  http://VM_IP:8000/
```

확인:
```bash
curl http://VM_IP:8000/health
# {"version":"...","buildings_loaded":695780}  ← 70만 가까이면 성공
```

---

## 5. 앱 연결

PC 의 `app/gradle.properties` 한 줄만 바꾼다(끝에 `/` 필수):
```properties
shelter.apiBaseUrl=http://VM_IP:8000/
```
그리고 앱을 다시 빌드/설치하면 서울 전역이 서버에서 온다.
(서버가 꺼지면 자동으로 강남 온디바이스로 폴백.)

---

## 6. (선택) 기상청 실데이터

기상청 API 키가 있으면:
```bash
export SHELTER_KMA_SERVICE_KEY=발급받은키
docker compose up -d        # 환경변수 반영해 재기동
```
없으면 계절/시각 기반 stub 으로 동작한다.

---

## 운영 메모

- **데이터 갱신**: 새 SHP 를 받아 `shp_to_buildings.py` 로 다시 변환 → `.gz` scp →
  `bash deploy/oracle-setup.sh`(멱등, `--replace` 로 재적재).
- **재부팅 후**: `docker compose up -d` 만 다시. 데이터는 `postgis_data` 볼륨에 영속.
- **보행망(OSM) 라우팅**: 현재는 직선/격자. 권역별 보행망을 쓰려면
  `shade-engine/scripts/fetch_walk_network.py` 로 받아 `SHELTER_WALK_NETWORK_GEOJSON`
  지정(docker-compose 의 environment). 미지정이어도 그늘 계산은 정상.
- **HTTPS**: 지금은 평문 HTTP(앱 매니페스트가 cleartext 허용). 공개 서비스로 키우면
  Caddy/Nginx 리버스 프록시 + 도메인으로 TLS 를 붙이고 앱 주소를 https 로 바꾼다.
- **성능**: PostGIS 저장소가 요청마다 새 커넥션을 연다(MVP 수준). 트래픽이 커지면
  커넥션 풀(psycopg_pool) + 그늘 타일 사전계산을 검토(docs/PRODUCTION.md C 항목).
