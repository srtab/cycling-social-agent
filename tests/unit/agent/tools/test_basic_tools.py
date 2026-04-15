"""Tests for the data-fetch tool builders."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cycling_agent.agent.tools.content_tools import build_content_tools
from cycling_agent.agent.tools.media_tools import build_media_tools
from cycling_agent.agent.tools.strava_tools import build_strava_tools
from cycling_agent.db.engine import build_engine, build_session_factory, init_schema
from cycling_agent.db.models import Language, Sponsor, StyleExample
from cycling_agent.db.repo import Repository
from cycling_agent.strava.client import StravaActivity


@pytest.fixture()
def repo() -> Repository:
    engine = build_engine(":memory:")
    init_schema(engine)
    return Repository(build_session_factory(engine))


def _activity(id_: int = 1) -> StravaActivity:
    return StravaActivity(
        id=id_,
        name=f"Race {id_}",
        workout_type=11,
        started_at=dt.datetime(2026, 4, 1, 10, 0, tzinfo=dt.UTC),
        distance_m=158420,
        moving_time_s=12640,
        elevation_gain_m=1834,
        avg_speed_mps=12.5,
        avg_power_w=268,
        norm_power_w=305,
        avg_hr=162,
        max_hr=188,
        kilojoules=3387,
        feeling_text=None,
        polyline="abc",
    )


def test_list_new_races_returns_unprocessed(repo: Repository) -> None:
    repo.upsert_activity(id=1, started_at=dt.datetime(2026, 4, 1), name="Race", workout_type=11)
    fake_strava = MagicMock()
    poller = MagicMock()
    poller.poll.return_value = [1]
    tools = build_strava_tools(repo=repo, client=fake_strava, poller=poller)
    list_new = next(t for t in tools if t.name == "list_new_races")
    result = list_new.invoke({})
    assert "1" in result


def test_get_activity_detail_returns_summary_fields(repo: Repository) -> None:
    fake_strava = MagicMock()
    fake_strava.get_activity_detail.return_value = _activity()
    poller = MagicMock()
    tools = build_strava_tools(repo=repo, client=fake_strava, poller=poller)
    get_detail = next(t for t in tools if t.name == "get_activity_detail")
    result = get_detail.invoke({"activity_id": 1})
    assert "158.4 km" in result or "158.42" in result
    assert "Race 1" in result


def test_get_feeling_returns_stored_text(repo: Repository) -> None:
    repo.upsert_activity(id=1, started_at=dt.datetime(2026, 4, 1), name="Race", workout_type=11)
    repo.set_feeling_text(activity_id=1, text="rainy crit, top 20")
    tools = build_strava_tools(repo=repo, client=MagicMock(), poller=MagicMock())
    get_feeling = next(t for t in tools if t.name == "get_feeling")
    result = get_feeling.invoke({"activity_id": 1})
    assert "rainy crit" in result


def test_read_sponsors_returns_all(repo: Repository) -> None:
    repo.replace_sponsors(
        [
            Sponsor(name="A", handle_facebook="@a", handle_instagram="@a", hashtag="#a"),
            Sponsor(name="B", handle_facebook="@b", handle_instagram="@b", hashtag="#b"),
        ]
    )
    tools = build_content_tools(repo=repo)
    read_sponsors = next(t for t in tools if t.name == "read_sponsors")
    result = read_sponsors.invoke({})
    assert "A" in result and "B" in result


def test_read_style_examples_returns_pt(repo: Repository) -> None:
    repo.replace_style_examples(
        [
            StyleExample(language=Language.PT, text="Texto em PT"),
        ]
    )
    tools = build_content_tools(repo=repo)
    read_style = next(t for t in tools if t.name == "read_style_examples")
    result = read_style.invoke({"language": "pt"})
    assert "Texto em PT" in result


def test_render_stats_card_writes_file(repo: Repository, tmp_path: Path) -> None:
    fake_strava = MagicMock()
    fake_strava.get_activity_detail.return_value = _activity()
    media_dir = tmp_path / "media"
    tools = build_media_tools(repo=repo, strava=fake_strava, media_dir=media_dir)
    render = next(t for t in tools if t.name == "render_stats_card")
    out_path_str = render.invoke({"activity_id": 1})
    assert Path(out_path_str).exists()
    assert Path(out_path_str).suffix == ".png"


def test_render_route_map_writes_file(repo: Repository, tmp_path: Path) -> None:
    fake_strava = MagicMock()
    fake_strava.get_activity_detail.return_value = _activity()
    media_dir = tmp_path / "media"
    # Stub the renderer so we don't hit the network for tiles.
    from cycling_agent.media.route_map import RouteMapRenderer

    real = RouteMapRenderer.render

    def stub_render(self, *, polyline: str, out_path: Path) -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 50)
        return out_path

    RouteMapRenderer.render = stub_render  # type: ignore[method-assign]
    try:
        tools = build_media_tools(repo=repo, strava=fake_strava, media_dir=media_dir)
        render = next(t for t in tools if t.name == "render_route_map")
        out_path_str = render.invoke({"activity_id": 1})
        assert Path(out_path_str).exists()
    finally:
        RouteMapRenderer.render = real  # type: ignore[method-assign]
