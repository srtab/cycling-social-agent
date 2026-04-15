"""Render the activity route as a PNG using py-staticmaps.

Decodes the Strava `summary_polyline` and renders an OSM-tile background
with the route overlaid. Network is required at render time to fetch tiles
unless a custom context factory is injected (used in tests).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import polyline as polyline_lib
import staticmaps

from cycling_agent.media._staticmaps_compat import apply as _apply_staticmaps_compat

_apply_staticmaps_compat()

_DEFAULT_SIZE = (1080, 1080)


def _default_context_factory() -> Any:
    ctx = staticmaps.Context()
    ctx.set_tile_provider(staticmaps.tile_provider_OSM)
    return ctx


class RouteMapRenderer:
    def __init__(self, context_factory: Callable[[], Any] = _default_context_factory) -> None:
        self._context_factory = context_factory

    def render(self, *, polyline: str, out_path: Path) -> Path:
        if not polyline:
            raise ValueError("polyline is empty; cannot render route map")
        coords = polyline_lib.decode(polyline)
        if not coords:
            raise ValueError("polyline decoded to no coordinates")

        ctx = self._context_factory()
        line = staticmaps.Line(
            [staticmaps.create_latlng(lat, lon) for lat, lon in coords],
            color=staticmaps.parse_color("#FF823C"),
            width=4,
        )
        ctx.add_object(line)
        img = ctx.render_pillow(*_DEFAULT_SIZE)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(out_path, "PNG")
        return out_path
