"""Tests for the stats card renderer."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from PIL import Image

from cycling_agent.media.stats_card import StatsCardRenderer
from cycling_agent.strava.client import StravaActivity


def _activity() -> StravaActivity:
    return StravaActivity(
        id=1, name="Volta ao Algarve - Etapa 2", workout_type=11,
        started_at=dt.datetime(2026, 2, 19, 13, 30, tzinfo=dt.UTC),
        distance_m=158420, moving_time_s=12640, elevation_gain_m=1834,
        avg_speed_mps=12.5, avg_power_w=268, norm_power_w=305,
        avg_hr=162, max_hr=188, kilojoules=3387, feeling_text=None, polyline="abc",
    )


def test_render_creates_png_at_expected_path(tmp_path: Path) -> None:
    out = tmp_path / "card.png"
    StatsCardRenderer().render(_activity(), out)
    assert out.exists()
    img = Image.open(out)
    assert img.format == "PNG"


def test_render_dimensions_are_1080x1080(tmp_path: Path) -> None:
    out = tmp_path / "card.png"
    StatsCardRenderer().render(_activity(), out)
    assert Image.open(out).size == (1080, 1080)


def test_render_handles_missing_power(tmp_path: Path) -> None:
    out = tmp_path / "card.png"
    a = _activity()
    no_power = StravaActivity(**{**a.__dict__, "avg_power_w": None, "norm_power_w": None})
    StatsCardRenderer().render(no_power, out)
    assert out.exists()
