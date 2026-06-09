#!/usr/bin/env bash
# Shelter — Oracle Cloud Always Free VM 부트스트랩.
#
# Ubuntu 22.04 (Ampere ARM, "VM.Standard.A1.Flex") 기준. 한 번만 실행하면
# Docker 설치 → 방화벽 개방 → 스택 기동 → 서울 전역 건물 PostGIS 적재까지 끝낸다.
#
# 사용:
#   1) 이 저장소를 VM 에 clone:   git clone <repo> shelter && cd shelter
#   2) 변환한 데이터(또는 .gz)를 backend/data/ 에 둔다 (로컬에서 scp).
#   3) bash deploy/oracle-setup.sh
#
# 멱등(idempotent): 다시 실행해도 안전하다.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

GEOJSON="backend/data/seoul_all_buildings.geojson"
DSN="postgresql://shelter:shelter@postgis:5432/shelter"

log() { printf '\n\033[1;32m[setup]\033[0m %s\n' "$*"; }

# ── 1. Docker + compose 플러그인 ──────────────────────────────────────────────
if ! command -v docker >/dev/null 2>&1; then
  log "Docker 설치"
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER" || true
fi
# compose v2 플러그인 확인
if ! docker compose version >/dev/null 2>&1; then
  log "docker compose 플러그인 설치"
  sudo apt-get update -y && sudo apt-get install -y docker-compose-plugin
fi

# ── 2. 방화벽: 8000 개방 (Oracle 은 기본 iptables 가 막혀 있다) ────────────────
# 주의: 콘솔의 VCN > 보안목록 인그레스 규칙(0.0.0.0/0 TCP 8000)도 반드시 추가해야 한다.
log "호스트 방화벽 8000/tcp 개방"
sudo iptables -C INPUT -p tcp --dport 8000 -j ACCEPT 2>/dev/null \
  || sudo iptables -I INPUT 6 -p tcp --dport 8000 -j ACCEPT
# 영속화(netfilter-persistent 있으면)
sudo netfilter-persistent save 2>/dev/null || true

# ── 3. 데이터 압축 해제 ───────────────────────────────────────────────────────
if [[ ! -f "$GEOJSON" && -f "$GEOJSON.gz" ]]; then
  log "GeoJSON 압축 해제"
  gunzip -k "$GEOJSON.gz"
fi
if [[ ! -f "$GEOJSON" ]]; then
  echo "ERROR: $GEOJSON 가 없습니다. 로컬에서 scp 로 올려주세요." >&2
  exit 1
fi

# ── 4. 스택 빌드 & 기동 ───────────────────────────────────────────────────────
log "docker compose 빌드/기동 (postgis + backend)"
sg docker -c "docker compose up -d --build" 2>/dev/null \
  || docker compose up -d --build   # 이미 docker 그룹이면 sg 불필요

log "postgis 헬스체크 대기"
until docker compose exec -T postgis pg_isready -U shelter -d shelter >/dev/null 2>&1; do
  sleep 2; printf '.'
done
echo

# ── 5. 서울 전역 건물 적재 (멱등: --replace 로 매번 새로 채움) ─────────────────
COUNT=$(docker compose exec -T postgis psql -U shelter -d shelter -tAc \
  "SELECT COUNT(*) FROM buildings" 2>/dev/null || echo 0)
log "현재 건물 행수: ${COUNT}. 적재 시작(약 70만 동, COPY)"
docker compose exec -T backend python -m app.db.ingest \
  --dsn "$DSN" \
  --buildings "/app/$GEOJSON" \
  --pois "/app/backend/data/sample_pois.geojson" \
  --replace

# ── 6. 확인 ───────────────────────────────────────────────────────────────────
log "헬스체크"
curl -fsS "http://localhost:8000/health" && echo
PUBIP=$(curl -fsS https://api.ipify.org 2>/dev/null || echo "<VM_PUBLIC_IP>")
cat <<EOF

✅ 완료. 외부 접속 주소:  http://${PUBIP}:8000/

앱 연결: PC 의 app/gradle.properties 에서
    shelter.apiBaseUrl=http://${PUBIP}:8000/
로 바꾸고 앱을 다시 빌드하세요. (끝에 / 필수)

KMA(기상청) 실데이터를 쓰려면:
    export SHELTER_KMA_SERVICE_KEY=발급키 && docker compose up -d
EOF
