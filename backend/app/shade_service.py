"""그늘 판정 서비스 — 경로 획득 → shade_engine → 응답 조립 + 캐싱."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from shade_engine.comfort import comfort_score
from shade_engine.engine import compute_route_shade
from shade_engine.geo import haversine_m
from shade_engine.osm_graph import OsmGraph
from shade_engine.osm_routing import RouteNotFound, plan_routes_osm
from shade_engine.routing import plan_routes
from shade_engine.suggest import best_departure, evaluate_departures
from shade_engine.sun import solar_position

from .buildings_repo import BuildingsRepository
from .cache import LRUCache, route_cache_key, routes_cache_key
from .config import Settings
from .directions import DirectionsProvider
from .models import (
    MODE_SPEED_MPS,
    DepartureCandidateOut,
    DepartureSuggestRequest,
    DepartureSuggestResponse,
    LatLng,
    Poi,
    RouteOptionOut,
    RoutesRequest,
    RoutesResponse,
    SegmentOut,
    ShadeRequest,
    ShadeResponse,
    WeatherBadge,
)
from .pois_repo import GeoJSONPoisRepository
from .trees_repo import TreesRepository
from .weather import WeatherProvider, get_weather_provider

_DEFAULT_SUGGEST_HOURS = [8, 10, 12, 14, 16, 18]
_KST = timezone(timedelta(hours=9))

# 폭주/오용 방지 입력 상한
_MAX_INPUT_COORDS = 5000
_MAX_SHADE_ROUTE_M = 50_000.0  # /v1/shade 경로 총길이 상한(50km)
_MAX_PLAN_ROUTE_M = 12_000.0  # /v1/routes·departure-suggest 직선거리 상한(앱 캡보다 약간 높은 안전장치)


def _polyline_length_m(coords: list[LatLng]) -> float:
    return sum(
        haversine_m(coords[i].lat, coords[i].lon, coords[i + 1].lat, coords[i + 1].lon)
        for i in range(len(coords) - 1)
    )

_M_PER_DEG_LAT = 111_320.0


class ShadeService:
    def __init__(
        self,
        repo: BuildingsRepository,
        provider: DirectionsProvider,
        settings: Settings,
        cache: LRUCache | None = None,
        weather: WeatherProvider | None = None,
        pois: GeoJSONPoisRepository | None = None,
        walk_graph: OsmGraph | None = None,
        trees: TreesRepository | None = None,
    ) -> None:
        self.repo = repo
        self.provider = provider
        self.settings = settings
        self.cache = cache or LRUCache(settings.cache_max_entries)
        self.weather = weather or get_weather_provider()
        self._pois = pois
        self.walk_graph = walk_graph
        self._trees = trees

    def _resolve_coords(self, req: ShadeRequest) -> list[LatLng]:
        if req.coords and len(req.coords) >= 2:
            return req.coords
        assert req.origin is not None and req.destination is not None  # validator 보장
        coords = self.provider.route(req.origin, req.destination, req.mode)
        if len(coords) < 2:
            raise ValueError("경로 탐색 결과가 비어 있습니다.")
        return coords

    def _bbox_with_margin(
        self, coords: list[LatLng]
    ) -> tuple[float, float, float, float]:
        lats = [c.lat for c in coords]
        lons = [c.lon for c in coords]
        mean_lat = sum(lats) / len(lats)
        margin = self.settings.bbox_margin_m
        dlat = margin / _M_PER_DEG_LAT
        dlon = margin / (_M_PER_DEG_LAT * max(0.1, math.cos(math.radians(mean_lat))))
        return (min(lats) - dlat, min(lons) - dlon, max(lats) + dlat, max(lons) + dlon)

    def _query_route_buildings(self, coords: list[LatLng], radius_m: float):
        """경로 주변 건물 조회. 저장소가 코리도 질의를 지원하면 라인 버퍼(좁은 띠)로,
        아니면 bbox 사각형으로. 긴 대각선 경로에서 코리도가 건물 수를 크게 줄인다."""
        qc = getattr(self.repo, "query_corridor", None)
        if qc is not None:
            try:
                return qc([(c.lat, c.lon) for c in coords], radius_m)
            except Exception:
                pass  # 코리도 질의 실패 시 bbox 로 안전 폴백
        min_lat, min_lon, max_lat, max_lon = self._bbox_with_margin(coords)
        return self.repo.query_bbox(min_lat, min_lon, max_lat, max_lon)

    def _query_route_trees(self, coords: list[LatLng]):
        """경로 주변 가로수 조회(미설정이면 빈 리스트). 7m 안팎의 가로수는 그림자가
        짧아 경로 bbox(+margin) 안만 봐도 충분하다."""
        if self._trees is None:
            return []
        min_lat, min_lon, max_lat, max_lon = self._bbox_with_margin(coords)
        return self._trees.query_bbox(min_lat, min_lon, max_lat, max_lon)

    def _plan_raw_options(
        self,
        origin_ll: tuple[float, float],
        dest_ll: tuple[float, float],
        mode: str,
        depart: datetime,
        prefer: str,
        grid_spacing_m: float,
        buildings: list,
        sun,
        speed: float,
    ):
        """OSM 보행 그래프(도보) 우선 → 실패 시 격자 폴백으로 경로 후보를 만든다.

        /v1/routes 와 /v1/departure-suggest 가 '동일한' 라우팅을 쓰도록 공유한다
        (추천 출발시각이 실제로 사용자가 걷는 경로와 일치하게). (raw_options, routing) 반환.
        """
        od_m = haversine_m(origin_ll[0], origin_ll[1], dest_ll[0], dest_ll[1])
        raw_options = None
        routing = "grid"
        if mode == "walk" and self.walk_graph is not None and self.walk_graph.node_count() > 0:
            try:
                raw_options = plan_routes_osm(
                    self.walk_graph,
                    origin_ll,
                    dest_ll,
                    buildings,
                    sun.azimuth_deg,
                    sun.altitude_deg,
                    prefer_sun=(prefer == "sun"),
                    depart=depart,
                    speed_mps=speed,
                )
                routing = "osm"
            except RouteNotFound:
                raw_options = None

        if raw_options is None:
            # 격자 라우팅 비용은 면적(거리²)에 비례해 폭증한다. 긴 경로는 격자 간격을
            # 넓혀 노드 수를 억제(짧은 경로는 요청값 그대로라 정밀도 유지).
            effective_spacing = max(grid_spacing_m, min(120.0, od_m / 80.0))
            raw_options = plan_routes(
                origin_ll,
                dest_ll,
                buildings,
                sun.azimuth_deg,
                sun.altitude_deg,
                grid_spacing_m=effective_spacing,
                prefer_sun=(prefer == "sun"),
                depart=depart,
                speed_mps=speed,
            )
        return raw_options, routing

    @staticmethod
    def _pick_option(raw_options: list, prefer: str):
        """선호(여름=그늘 최적/겨울=햇빛 최적)에 해당하는 대표 경로 1개. 없으면 균형/첫번째."""
        target = "sunniest" if prefer == "sun" else "shadiest"
        by_name = {o.name: o for o in raw_options}
        return by_name.get(target) or by_name.get("balanced") or raw_options[0]

    def compute(self, req: ShadeRequest) -> ShadeResponse:
        coords = self._resolve_coords(req)
        if len(coords) > _MAX_INPUT_COORDS:
            raise ValueError(f"경로 좌표가 너무 많습니다(최대 {_MAX_INPUT_COORDS}).")
        if _polyline_length_m(coords) > _MAX_SHADE_ROUTE_M:
            raise ValueError("경로가 너무 깁니다(최대 50km).")
        depart = req.depart_time or datetime.now(timezone.utc)

        key = route_cache_key(coords, depart, req.mode, req.spacing_m, req.moving_sun)
        cached = self.cache.get(key)
        if isinstance(cached, ShadeResponse):
            return cached.model_copy(update={"cached": True})

        # 실제 경로(coords) 주변 좁은 띠만 조회(그림자 도달 고려해 margin+여유).
        buildings = self._query_route_buildings(coords, radius_m=self.settings.bbox_margin_m + 100.0)
        trees = self._query_route_trees(coords)

        route_shade = compute_route_shade(
            [(c.lat, c.lon) for c in coords],
            depart,
            buildings,
            spacing_m=req.spacing_m,
            moving_sun=req.moving_sun,
            walk_speed_mps=MODE_SPEED_MPS.get(req.mode, MODE_SPEED_MPS["walk"]),
            trees=trees,
        )

        segments = _segments_from_shade(route_shade)

        response = ShadeResponse(
            shade_percent=route_shade.shade_percent,
            total_distance_m=round(route_shade.total_distance_m, 1),
            sample_count=route_shade.total_count,
            mean_confidence=round(route_shade.mean_confidence, 3),
            depart_time=depart,
            mode=req.mode,
            provider=self.provider.name if not req.coords else "explicit",
            building_count=len(buildings),
            cached=False,
            segments=segments,
        )
        self.cache.set(key, response)
        return response

    def plan_route_options(self, req: RoutesRequest) -> RoutesResponse:
        """출발→도착에 대해 최단/균형/그늘 경로 후보를 만들고 각각 그늘을 색칠한다."""
        od_m = haversine_m(
            req.origin.lat, req.origin.lon, req.destination.lat, req.destination.lon
        )
        if od_m > _MAX_PLAN_ROUTE_M:
            raise ValueError(f"출발-도착 거리가 너무 깁니다(최대 {int(_MAX_PLAN_ROUTE_M // 1000)}km).")
        depart = req.depart_time or datetime.now(timezone.utc)

        key = routes_cache_key(
            req.origin, req.destination, depart, req.mode, req.prefer, req.grid_spacing_m
        )
        cached = self.cache.get(key)
        if isinstance(cached, RoutesResponse):
            return cached.model_copy(update={"cached": True})

        sun = solar_position(req.origin.lat, req.origin.lon, depart)

        # 격자 라우팅은 직선 주변을 탐색하므로, 직선 주변 코리도(경로 이탈 여유 포함)만 조회.
        corridor_m = min(900.0, max(400.0, 0.2 * od_m))
        buildings = self._query_route_buildings([req.origin, req.destination], radius_m=corridor_m)
        trees = self._query_route_trees([req.origin, req.destination])

        speed = MODE_SPEED_MPS.get(req.mode, MODE_SPEED_MPS["walk"])
        info = self.weather.badge(req.origin.lat, req.origin.lon, depart)

        origin_ll = (req.origin.lat, req.origin.lon)
        dest_ll = (req.destination.lat, req.destination.lon)

        # OSM 보행 그래프(도보) 우선 → 못 덮으면 격자 폴백. departure-suggest 와 동일 로직 공유.
        raw_options, routing = self._plan_raw_options(
            origin_ll, dest_ll, req.mode, depart, req.prefer, req.grid_spacing_m, buildings, sun, speed
        )

        options: list[RouteOptionOut] = []
        for opt in raw_options:
            shade = compute_route_shade(
                opt.coords, depart, buildings, spacing_m=10.0, walk_speed_mps=speed, trees=trees
            )
            options.append(
                RouteOptionOut(
                    name=opt.name,
                    distance_m=round(opt.distance_m, 1),
                    # 모드 평균속도 기준 예상 소요시간(분) — P0 비교축(거리·시간·그늘%).
                    duration_min=round(opt.distance_m / speed / 60.0, 1) if speed > 0 else 0.0,
                    shade_percent=shade.shade_percent,
                    comfort=comfort_score(shade.shade_fraction, info.temp_c, info.uv_index),
                    coords=[LatLng(lat=la, lon=lo) for la, lo in opt.coords],
                    segments=_segments_from_shade(shade),
                )
            )

        response = RoutesResponse(
            depart_time=depart,
            mode=req.mode,
            prefer=req.prefer,
            routing=routing,
            building_count=len(buildings),
            cached=False,
            weather=WeatherBadge(
                temp_c=info.temp_c,
                uv_index=info.uv_index,
                heat_advisory=info.heat_advisory,
                source=info.source,
            ),
            options=options,
        )
        self.cache.set(key, response)
        return response

    def suggest_departures(self, req: DepartureSuggestRequest) -> DepartureSuggestResponse:
        """후보 출발 시각별 그늘을 평가하고 최적 시각을 추천한다.

        평가 대상 경로는 /v1/routes 와 '동일한' OSM/격자 라우팅으로 만든다(예전엔
        직선 보간을 써서, 추천 시각이 실제로 사용자가 걷는 경로와 다른 길의 그늘을
        기준으로 계산되던 불일치가 있었다).
        """
        od_m = haversine_m(
            req.origin.lat, req.origin.lon, req.destination.lat, req.destination.lon
        )
        if od_m > _MAX_PLAN_ROUTE_M:
            raise ValueError(f"출발-도착 거리가 너무 깁니다(최대 {int(_MAX_PLAN_ROUTE_M // 1000)}km).")

        if req.date:
            try:
                y, m, d = (int(x) for x in req.date.split("-"))
            except ValueError as exc:
                raise ValueError("date 형식은 YYYY-MM-DD 여야 합니다.") from exc
        else:
            today = datetime.now(_KST)
            y, m, d = today.year, today.month, today.day

        hours = req.hours or _DEFAULT_SUGGEST_HOURS
        candidates = [datetime(y, m, d, h, 0, tzinfo=_KST) for h in hours]

        # 직선 코리도 내 건물/가로수로 라우팅 + 그늘 평가를 모두 수행.
        corridor_m = min(900.0, max(400.0, 0.2 * od_m))
        buildings = self._query_route_buildings([req.origin, req.destination], radius_m=corridor_m)
        trees = self._query_route_trees([req.origin, req.destination])
        speed = MODE_SPEED_MPS.get(req.mode, MODE_SPEED_MPS["walk"])

        # 대표 경로를 후보 중앙 시각에 라우팅해 얻고(선호=그늘/햇빛 최적 옵션 선택),
        # 그 고정 경로 위에서 후보 시각별 그늘을 평가한다.
        rep_depart = candidates[len(candidates) // 2]
        sun_rep = solar_position(req.origin.lat, req.origin.lon, rep_depart)
        raw_options, _ = self._plan_raw_options(
            (req.origin.lat, req.origin.lon),
            (req.destination.lat, req.destination.lon),
            req.mode,
            rep_depart,
            req.prefer,
            20.0,
            buildings,
            sun_rep,
            speed,
        )
        coords = self._pick_option(raw_options, req.prefer).coords
        if len(coords) < 2:
            raise ValueError("경로 탐색 결과가 비어 있습니다.")

        evals = evaluate_departures(
            coords, candidates, buildings, walk_speed_mps=speed, trees=trees
        )
        best = best_departure(evals, prefer_sun=(req.prefer == "sun"))
        assert best is not None  # candidates 비어있지 않음
        return DepartureSuggestResponse(
            best=DepartureCandidateOut(depart_time=best.depart, shade_percent=best.shade_percent),
            prefer=req.prefer,
            candidates=[
                DepartureCandidateOut(depart_time=e.depart, shade_percent=e.shade_percent)
                for e in evals
            ],
        )

    def find_pois(
        self, min_lat: float, min_lon: float, max_lat: float, max_lon: float
    ) -> list[Poi]:
        if self._pois is None:
            self._pois = GeoJSONPoisRepository(self.settings.pois_geojson)
        return self._pois.query_bbox(min_lat, min_lon, max_lat, max_lon)


def _segments_from_shade(route_shade) -> list[SegmentOut]:
    return [
        SegmentOut(
            a=LatLng(lat=s.lat, lon=s.lon),
            b=LatLng(lat=nxt.lat, lon=nxt.lon),
            shaded=s.result.shaded,
            reason=s.result.reason,
            confidence=round(s.result.confidence, 3),
        )
        for s, nxt in zip(route_shade.samples, route_shade.samples[1:])
    ]
