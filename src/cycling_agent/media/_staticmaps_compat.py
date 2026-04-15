"""Compatibility shim for py-staticmaps against Pillow >= 10.

``py-staticmaps`` 0.4.0 (the latest release) calls ``ImageDraw.textsize`` in
``PillowRenderer.render_attribution``. That method was removed in Pillow 10
(deprecated in 9.2), so every call to ``Context.render_pillow`` raises
``AttributeError`` on modern Pillow. Upstream is effectively unmaintained.

``apply()`` replaces the method in-place with a ``textbbox``-based
implementation that is equivalent under Pillow's default font. It is
idempotent and safe to call on import.
"""

from __future__ import annotations

from PIL import Image as PIL_Image
from PIL import ImageDraw as PIL_ImageDraw
from staticmaps.pillow_renderer import PillowRenderer

_PATCHED_FLAG = "_cycling_agent_textsize_patched"


def _render_attribution(self: PillowRenderer, attribution: str | None) -> None:
    if not attribution:
        return
    margin = 2
    bbox = self.draw().textbbox((0, 0), attribution)
    th = bbox[3] - bbox[1]
    w = self._trans.image_width()
    h = self._trans.image_height()
    overlay = PIL_Image.new("RGBA", self._image.size, (255, 255, 255, 0))
    draw = PIL_ImageDraw.Draw(overlay)
    draw.rectangle([(0, h - th - 2 * margin), (w, h)], fill=(255, 255, 255, 204))
    self.alpha_compose(overlay)
    self.draw().text((margin, h - th - margin), attribution, fill=(0, 0, 0, 255))


def apply() -> None:
    """Patch ``PillowRenderer.render_attribution`` for Pillow >= 10. Idempotent."""
    if getattr(PillowRenderer, _PATCHED_FLAG, False):
        return
    PillowRenderer.render_attribution = _render_attribution  # type: ignore[method-assign]
    setattr(PillowRenderer, _PATCHED_FLAG, True)
