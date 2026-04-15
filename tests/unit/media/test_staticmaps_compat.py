"""Regression test for the py-staticmaps / Pillow >= 10 textsize bug.

``py-staticmaps`` 0.4.0 uses ``ImageDraw.textsize`` which was removed in
Pillow 10. Our compat shim patches ``PillowRenderer.render_attribution``
so it works on Pillow 10+. This test exercises that patched code path
directly.
"""

from __future__ import annotations

from PIL import Image, ImageDraw
from staticmaps.pillow_renderer import PillowRenderer

from cycling_agent.media._staticmaps_compat import apply


class _FakeTrans:
    def __init__(self, size: int = 100) -> None:
        self._size = size

    def image_width(self) -> int:
        return self._size

    def image_height(self) -> int:
        return self._size


def _build_renderer(size: int = 100) -> PillowRenderer:
    r = PillowRenderer.__new__(PillowRenderer)
    r._image = Image.new("RGBA", (size, size))
    r._draw = ImageDraw.Draw(r._image)
    r._trans = _FakeTrans(size)
    r._offset_x = 0
    return r


def test_render_attribution_runs_on_pillow_10_plus() -> None:
    apply()
    renderer = _build_renderer()
    # Pre-patch, this raised AttributeError: 'ImageDraw' object has no attribute 'textsize'
    renderer.render_attribution("Maps & Data (C) OpenStreetMap.org contributors")


def test_render_attribution_no_op_on_empty_attribution() -> None:
    apply()
    renderer = _build_renderer()
    renderer.render_attribution(None)
    renderer.render_attribution("")


def test_apply_is_idempotent() -> None:
    apply()
    first = PillowRenderer.render_attribution
    apply()
    assert PillowRenderer.render_attribution is first
