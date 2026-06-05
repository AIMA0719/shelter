"""그늘 판정 서비스 — 경로 획득 → shade_engine → 응답 조립 + 캐싱."""

from __future__ import annotations

import math
from datetime import datetime, timezone

from shade_engine.engine import compute_route_shade
from shade_engine.routing import plan_routes
from shade_engine.sun import solar_position

from .buildings_repo import BuildingsRepository
from .cache import LRUCache, route_cache_key
from .config import Settings
from .directions import DirectionsProvider
from .models import (
    MODE_SPEED_MPS,
    LatLng,
    RouteOptionOut,
    RoutesRequest,
    RoutesResponse,
    SegmentOut,
    ShadeRequest,
    ShadeResponse,
    WeatherBadge,
)
from .weather import WeatherProvider, get_weather_provider

_M_PER_DEG_LAT = 111_320.0


class ShadeService:
    def __init__(
        self,
        repo: BuildingsRepository,
        provider: DirectionsProvider,
        settings: Settings,
        cache: LRUCache | None = None,
        weather: WeatherProvider | None = None,
    ) -> None:
        self.repo = repo
        self.provider = provider
        self.settings = settings
        self.cache = cache or LRUCache(settings.cache_max_entries)
        self.weather = weather or get_weather_provider()

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

    def compute(self, req: ShadeRequest) -> ShadeResponse:
        coords = self._resolve_coords(req)
        depart = req.depart_time or datetime.now(timezone.utc)

        key = route_cache_key(coords, depart, req.mode, req.spacing_m, req.moving_sun)
        cached = self.cache.get(key)
        if isinstance(cached, ShadeResponse):
            return cached.model_copy(update={"cached": True})

        min_lat, min_lon, max_lat, max_lon = self._bbox_with_margin(coords)
        buildings = self.repo.query_bbox(min_lat, min_lon, max_lat, max_lon)

        route_shade = compute_route_shade(
            [(c.lat, c.lon) for c in coords],
            depart,
            buildings,
            spacing_m=req.spacing_m,
            moving_sun=req.moving_sun,
            walk_speed_mps=MODE_SPEED_MPS.get(req.mode, MODE_SPEED_MPS["walk"]),
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
        depart = req.depart_time or datetime.now(timezone.utc)
        sun = solar_position(req.origin.lat, req.origin.lon, depart)

        min_lat, min_lon, max_lat, max_lon = self._bbox_with_margin([req.origin, req.destination])
        buildings = self.repo.query_bbox(min_lat, min_lon, max_lat, max_lon)

        speed = MODE_SPEED_MPS.get(req.mode, MODE_SPEED_MPS["walk"])
        raw_options = plan_routes(
            (req.origin.lat, req.origin.lon),
            (req.destination.lat, req.destination.lon),
            buildings,
            sun.azimuth_deg,
            sun.altitude_deg,
            grid_spacing_m=req.grid_spacing_m,
        )

        options: list[RouteOptionOut] = []
        for opt in raw_options:
            shade = compute_route_shade(
                opt.coords, depart, buildings, spacing_m=10.0, walk_speed_mps=speed
            )
            options.append(
                RouteOptionOut(
                    name=opt.name,
                    distance_m=round(opt.distance_m, 1),
                    shade_percent=shade.shade_percent,
                    coords=[LatLng(lat=la, lon=lo) for la, lo in opt.coords],
                    segments=_segments_from_shade(shade),
                )
            )

        info = self.weather.badge(req.origin.lat, req.origin.lon, depart)
        return RoutesResponse(
            depart_time=depart,
            mode=req.mode,
            building_count=len(buildings),
            weather=WeatherBadge(
                temp_c=info.temp_c,
                uv_index=info.uv_index,
                heat_advisory=info.heat_advisory,
                source=info.source,
            ),
            options=options,
        )


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
