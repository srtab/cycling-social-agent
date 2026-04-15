"""Tests for the route map renderer (no network: stubbed staticmaps)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

from cycling_agent.media.route_map import RouteMapRenderer


def test_render_writes_png(tmp_path: Path) -> None:
    out = tmp_path / "map.png"
    fake_ctx = MagicMock()
    fake_ctx.render_pillow.return_value = Image.new("RGB", (1080, 1080), (200, 200, 200))
    builder = MagicMock(return_value=fake_ctx)
    renderer = RouteMapRenderer(context_factory=builder)
    renderer.render(polyline="}~p_F~ngzAhIb@", out_path=out)
    assert out.exists()
    builder.assert_called_once()


def test_render_raises_on_empty_polyline(tmp_path: Path) -> None:
    renderer = RouteMapRenderer()
    with pytest.raises(ValueError, match="polyline"):
        renderer.render(polyline="", out_path=tmp_path / "x.png")
