"""경로 그늘 결과를 Leaflet HTML 지도로 시각화 (선택적, 의존성 없음).

folium 등 외부 패키지 없이 Leaflet CDN 을 쓰는 단일 HTML 을 생성한다.
그늘 구간은 초록, 햇빛 구간은 주황으로 폴리라인을 색칠한다.
"""

from __future__ import annotations

import json

from .buildings import Building
from .engine import RouteShade

_SHADE_COLOR = "#2e7d32"  # 초록 = 그늘
_SUN_COLOR = "#f9a825"  # 주황 = 햇빛
_BUILDING_COLOR = "#90a4ae"


def route_shade_to_html(
    route: RouteShade,
    path: str,
    *,
    buildings: list[Building] | None = None,
    title: str = "Shelter 그늘 경로",
) -> str:
    """RouteShade → 색칠 폴리라인 Leaflet HTML 파일로 저장. 경로 문자열 반환."""
    segments = []
    for a, b in zip(route.samples, route.samples[1:]):
        segments.append(
            {
                "coords": [[a.lat, a.lon], [b.lat, b.lon]],
                "color": _SHADE_COLOR if a.result.shaded else _SUN_COLOR,
            }
        )

    building_rings = []
    if buildings:
        for bld in buildings:
            building_rings.append([[lat, lon] for lat, lon in bld.ring])

    center = (
        [route.samples[len(route.samples) // 2].lat, route.samples[len(route.samples) // 2].lon]
        if route.samples
        else [37.4979, 127.0276]
    )

    html = _TEMPLATE.format(
        title=title,
        center=json.dumps(center),
        segments=json.dumps(segments),
        buildings=json.dumps(building_rings),
        shade_color=_SHADE_COLOR,
        sun_color=_SUN_COLOR,
        building_color=_BUILDING_COLOR,
        shade_percent=route.shade_percent,
        distance=round(route.total_distance_m),
        confidence=round(route.mean_confidence * 100),
    )
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return path


_TEMPLATE = """<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"><title>{title}</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  html,body,#map{{height:100%;margin:0}}
  .panel{{position:absolute;z-index:1000;top:12px;left:12px;background:#fff;
    padding:10px 14px;border-radius:10px;font:14px/1.4 system-ui;box-shadow:0 2px 8px rgba(0,0,0,.2)}}
  .panel b{{font-size:18px}}
  .legend i{{display:inline-block;width:12px;height:12px;border-radius:2px;margin-right:4px}}
</style></head><body>
<div id="map"></div>
<div class="panel">
  <div><b>그늘 {shade_percent}%</b> · {distance} m</div>
  <div class="legend">
    <span><i style="background:{shade_color}"></i>그늘</span>&nbsp;
    <span><i style="background:{sun_color}"></i>햇빛</span>
  </div>
  <div style="color:#888;font-size:12px">신뢰도 {confidence}%</div>
</div>
<script>
  var map = L.map('map').setView({center}, 17);
  L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',
    {{maxZoom:19, attribution:'© OpenStreetMap'}}).addTo(map);
  {buildings}.forEach(function(r){{
    L.polygon(r, {{color:'{building_color}', weight:1, fillOpacity:0.25}}).addTo(map);
  }});
  {segments}.forEach(function(s){{
    L.polyline(s.coords, {{color:s.color, weight:6, opacity:0.9}}).addTo(map);
  }});
</script></body></html>"""
