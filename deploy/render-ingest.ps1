# Shelter — Render PostgreSQL 에 서울 전역 건물 적재 (PowerShell).
#
# 최초 적재 / 90일 후 DB 재생성 시 모두 이 스크립트 한 번이면 된다.
# DSN 은 Render 대시보드 → shelter-db → "External Database URL" 을 그대로 붙여넣는다.
#
# 사용:
#   .\deploy\render-ingest.ps1 -Dsn "postgresql://USER:PW@HOST/DB"
#
# 사전: python, psycopg(설치됨), 변환된 backend/data/seoul_all_buildings.geojson

param(
    [Parameter(Mandatory = $true)][string]$Dsn
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$geojson = Join-Path $repo "backend\data\seoul_all_buildings.geojson"

if (-not (Test-Path $geojson)) {
    $gz = "$geojson.gz"
    if (Test-Path $gz) {
        Write-Host "[ingest] gz 압축 해제..."
        # Windows 에 gzip 이 없을 수 있어 .NET 으로 해제
        $in = [System.IO.File]::OpenRead($gz)
        $out = [System.IO.File]::Create($geojson)
        $gzs = New-Object System.IO.Compression.GzipStream($in, [System.IO.Compression.CompressionMode]::Decompress)
        $gzs.CopyTo($out); $gzs.Close(); $out.Close(); $in.Close()
    } else {
        throw "데이터가 없습니다: $geojson (또는 .gz). 먼저 SHP 변환을 실행하세요."
    }
}

Push-Location (Join-Path $repo "backend")
try {
    # Render 외부 접속은 SSL 필요. shade_engine import 위해 PYTHONPATH 에 shade-engine 추가.
    $env:PYTHONPATH = (Join-Path $repo "shade-engine")
    $dsnSsl = if ($Dsn -match "sslmode=") { $Dsn } else { "$Dsn`?sslmode=require" }

    Write-Host "[ingest] 스키마 생성 + 서울 전역 건물 적재 (수 분 소요)..."
    python -m app.db.ingest `
        --dsn $dsnSsl `
        --init-schema "app\db\schema.sql" `
        --buildings "data\seoul_all_buildings.geojson" `
        --pois "data\sample_pois.geojson" `
        --replace
    if ($LASTEXITCODE -ne 0) { throw "ingest 실패 (exit $LASTEXITCODE)" }
    Write-Host "`n[ingest] ✅ 완료. https://<your-service>.onrender.com/health 에서 buildings_loaded 확인."
}
finally {
    Pop-Location
}
