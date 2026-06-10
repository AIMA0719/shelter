# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Shelter (가칭 「그늘로」) — a walking/cycling route app that tells you **where shade vs. sunlight is** along a route and recommends the **shadiest path** to a destination. Korean is the primary language for docs, comments, and commit messages.

See `docs/PRD.md` (product) and `docs/DEV_PLAN.md` (phased plan). Code comments are extensive and in Korean — read them; they explain non-obvious tradeoffs.

## Monorepo layout

Three independent packages with a one-way dependency chain:

```
shade-engine/  ← pure-Python shade core (stdlib only). NO knowledge of HTTP/DB.
backend/       ← FastAPI service. Imports shade_engine as a sibling package.
app/           ← Kotlin/Compose Android app (Naver Maps SDK). Talks to backend over HTTP.
```

`backend` depends on `shade-engine`; `app` depends on `backend`'s HTTP API. The engine never imports backend code — keep domain logic (sun geometry, raycasting, routing) in `shade-engine` and only orchestration/IO (route fetching, caching, response assembly, repos) in `backend`.

### How backend finds shade_engine

`backend` imports `shade_engine` as a sibling package, **not** a pip dependency. `backend/app/config.py` inserts `../shade-engine` into `sys.path` at import time, and `backend/pyproject.toml` sets `pythonpath = [".", "../shade-engine"]` for pytest. When running uvicorn manually, set `PYTHONPATH=../shade-engine`.

## Commands

```bash
# shade-engine
cd shade-engine && python -m pip install -e ".[dev]" && pytest
pytest tests/test_sun.py::test_name      # single test
python -m shade_engine.demo              # morning/noon/afternoon shade% demo

# backend
cd backend && python -m pip install -r requirements.txt
PYTHONPATH=../shade-engine uvicorn app.main:app --port 8000
pytest                                   # pythonpath set via pyproject

# Android (or open app/ in Android Studio)
cd app && ./gradlew :app:assembleDebug :app:testDebugUnitTest
```

CI (`.github/workflows/ci.yml`) runs only the two Python test suites (Python 3.11) on every push/PR; the Android build is not in CI.

## Core domain model (shade-engine)

The whole product reduces to one geometric idea: **shade = relation between the sun's geometry (azimuth/altitude) and light-blocking objects (buildings, street trees).** From a point, cast a ray toward the sun; at distance `d`, if a building's height ≥ `d × tan(altitude)`, the point is shaded.

Pipeline through the engine modules:
- `sun.py` — solar position (NOAA algorithm), pure math.
- `buildings.py` — building polygons + height estimation; spatial index for fast lookup.
- `raycast.py` — `is_point_shaded()`: the ray/height test above.
- `engine.py` — `compute_route_shade()`: samples a polyline and produces per-segment shade + overall shade%.
- `routing.py` (grid) / `osm_routing.py` (OSM walk graph) — shade-weighted Dijkstra. **Edge cost = distance × (1 + α·sunlit_fraction)**; higher α → shadier route (same principle as Valhalla custom costing). `prefer_sun` inverts it for the winter "sunlight" mode.
- `osm_graph.py` — loads an OSM pedestrian network (LineString GeoJSON) into a routable graph.
- `suggest.py` (departure-time recommendation), `comfort.py` (comfort score), `trees.py` (street trees modeled as low buildings).

## Backend service flow

`backend/app/main.py` is the FastAPI app (factory `create_app`). `ShadeService` (`shade_service.py`) is the orchestration hub for every endpoint: resolve route coords → query nearby buildings → call `shade_engine` → assemble response → LRU-cache.

Endpoints: `GET /health`, `POST /v1/shade` (single-route shading), `POST /v1/routes` (shortest/balanced/shade route comparison + comfort + weather), `POST /v1/departure-suggest`, `GET /v1/pois`.

Key runtime switches, all driven by env vars in `config.py` (`SHELTER_*`), resolved once in `build_service()`:
- **Buildings/POIs repo**: `SHELTER_DB_DSN` set → PostGIS (Seoul-wide); else GeoJSON files (MVP/sample). Repos share the `BuildingsRepository` interface; PostGIS additionally implements `query_corridor` (narrow line-buffer query) which the service prefers over bbox for long routes.
- **Routing**: `SHELTER_WALK_NETWORK_GEOJSON` set & file exists & mode is `walk` → OSM graph Dijkstra; otherwise the grid router (offline fallback). OSM `RouteNotFound` (graph doesn't cover origin/dest) also falls back to grid.
- **Weather**: `SHELTER_KMA_SERVICE_KEY` set → real 기상청 (KMA) data; else stub.

Performance is constrained by a free-tier CPU, which drives many choices in `shade_service.py`: corridor queries instead of bbox to cut building counts, adaptive grid spacing that widens on long routes (grid cost grows with area ≈ distance²), and input caps (`_MAX_*` constants — e.g. 12 km plan-route limit as a safety net below the app's own cap). When changing routing/query logic, preserve these guards.

## Data ingestion (PostGIS path)

Schema: `backend/app/db/schema.sql` (PostGIS extension + tables). Applied automatically by docker-compose on first DB init, or manually for managed DBs. Ingest GeoJSON → PostGIS:

```bash
python -m app.db.ingest --dsn "postgresql://shelter:shelter@localhost:5432/shelter" \
    --buildings data/<area>_buildings.geojson --pois data/sample_pois.geojson [--replace] [--init-schema app/db/schema.sql]
```

Local stack: `docker compose up -d` (PostGIS + backend). Render deploy: `deploy/render-ingest.ps1 -Dsn <external-dsn>` (handles `.gz` decompression + SSL). Source building data is fetched/converted via `shade-engine/scripts/` (Overpass, V-World SHP).

## Android app

Single module `app/app` (`com.shelter.shade`), Compose + Naver Maps SDK, minSdk 26 / targetSdk 34, JVM 17.
- `engine/` mirrors the Python engine — an **on-device shade fallback** (`LocalShadeEngine`) using bundled `assets/seoul_gangnam_*.geojson`, so the app works offline if the backend is unreachable.
- **Secrets are not committed.** Naver NCP key comes from `local.properties` (`NCP_KEY_ID`) → injected as a manifest placeholder. Backend URL from gradle property `shelter.apiBaseUrl` (default `http://10.0.2.2:8000/`, the emulator's host alias) → `BuildConfig.API_BASE_URL`.

## Conventions

- Each phase (0–3) was reviewed by an independent Codex (OpenAI) pass; review findings were fixed and turned into regression tests. New behavior should likewise land with a test.
- Commit messages: Korean, conventional-commit prefixes scoped by package — `feat(app)`, `perf(backend)`, etc.
- Keep the engine dependency-free (stdlib only; `dev`/`gis` extras are optional). Don't add runtime deps to `shade-engine`.
