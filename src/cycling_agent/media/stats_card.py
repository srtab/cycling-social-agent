"""Render a square stats card image for a Strava activity.

Pillow-based. Uses the default DejaVu font shipped with Pillow so the
renderer has no external font dependency.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from cycling_agent.strava.client import StravaActivity

_SIZE = (1080, 1080)
_BG = (15, 18, 26)
_FG = (240, 240, 245)
_ACCENT = (255, 130, 60)


class StatsCardRenderer:
    """Render a single 1080x1080 PNG stats card."""

    def render(self, activity: StravaActivity, out_path: Path) -> Path:
        img = Image.new("RGB", _SIZE, _BG)
        draw = ImageDraw.Draw(img)

        title_font = _font(64)
        body_font = _font(48)
        small_font = _font(32)

        draw.text((60, 60), activity.name[:36], font=title_font, fill=_FG)
        draw.text(
            (60, 140),
            activity.started_at.strftime("%d %b %Y"),
            font=small_font,
            fill=_ACCENT,
        )

        rows = _stat_rows(activity)
        y = 240
        for label, value in rows:
            draw.text((60, y), label, font=small_font, fill=_ACCENT)
            draw.text((60, y + 36), value, font=body_font, fill=_FG)
            y += 130

        out_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(out_path, "PNG")
        return out_path


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _stat_rows(a: StravaActivity) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    rows.append(("DISTANCE", f"{a.distance_m / 1000:.1f} km"))
    rows.append(("TIME", _fmt_duration(a.moving_time_s)))
    rows.append(("ELEVATION", f"{int(a.elevation_gain_m)} m"))
    if a.avg_power_w is not None:
        np = f" / NP {int(a.norm_power_w)} W" if a.norm_power_w else ""
        rows.append(("POWER", f"AVG {int(a.avg_power_w)} W{np}"))
    if a.avg_hr is not None:
        rows.append(("HEART RATE", f"AVG {int(a.avg_hr)} bpm"))
    return rows


def _fmt_duration(seconds: int) -> str:
    delta = dt.timedelta(seconds=seconds)
    h, rem = divmod(int(delta.total_seconds()), 3600)
    m, _ = divmod(rem, 60)
    return f"{h}h {m:02d}m"
