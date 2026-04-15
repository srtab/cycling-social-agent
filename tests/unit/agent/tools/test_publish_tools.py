"""Tests for publish-related agent tools."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from freezegun import freeze_time

from cycling_agent.agent.tools.publish_tools import build_publish_tools
from cycling_agent.db.engine import build_engine, build_session_factory, init_schema
from cycling_agent.db.models import DraftStatus, Language, Platform
from cycling_agent.db.repo import Repository


@pytest.fixture()
def repo() -> Repository:
    engine = build_engine(":memory:")
    init_schema(engine)
    repo = Repository(build_session_factory(engine))
    repo.upsert_activity(id=1, started_at=dt.datetime(2026, 4, 1), name="Crit", workout_type=11)
    return repo


def _approved_draft(repo: Repository, *, platform: Platform = Platform.FACEBOOK) -> int:
    did = repo.create_draft(
        activity_id=1, platform=platform, language=Language.PT,
        caption="x", media_paths="/tmp/a.png",
    )
    repo.set_approved(did, post_now=False)
    return did


def test_schedule_publish_sets_scheduled_for_today_when_in_future(repo: Repository) -> None:
    did = _approved_draft(repo)
    publishers = {Platform.FACEBOOK: MagicMock(), Platform.INSTAGRAM: MagicMock()}
    tools = build_publish_tools(
        repo=repo, publishers=publishers,
        publish_time_local="19:00", publish_timezone="Europe/Lisbon",
    )
    schedule = next(t for t in tools if t.name == "schedule_publish")
    with freeze_time("2026-04-01 10:00:00", tz_offset=0):
        result = schedule.invoke({"draft_id": did})
    assert "scheduled" in result.lower()
    d = repo.get_draft(did)
    assert d is not None
    assert d.status == DraftStatus.SCHEDULED
    assert d.scheduled_for is not None


def test_schedule_publish_rolls_to_next_day_when_window_passed(repo: Repository) -> None:
    did = _approved_draft(repo)
    publishers = {Platform.FACEBOOK: MagicMock(), Platform.INSTAGRAM: MagicMock()}
    tools = build_publish_tools(
        repo=repo, publishers=publishers,
        publish_time_local="19:00", publish_timezone="Europe/Lisbon",
    )
    schedule = next(t for t in tools if t.name == "schedule_publish")
    with freeze_time("2026-04-01 22:00:00", tz_offset=0):
        schedule.invoke({"draft_id": did})
    d = repo.get_draft(did)
    assert d is not None
    assert d.scheduled_for is not None
    assert d.scheduled_for.day == 2


def test_publish_due_drafts_publishes_scheduled_past(repo: Repository, tmp_path: Path) -> None:
    img = tmp_path / "card.png"
    img.write_bytes(b"PNG")
    did = repo.create_draft(
        activity_id=1, platform=Platform.FACEBOOK, language=Language.PT,
        caption="x", media_paths=str(img),
    )
    repo.set_approved(did, post_now=False)
    repo.schedule_draft(did, dt.datetime(2026, 4, 1, 18, 0))

    fb = MagicMock()
    fb.publish.return_value = "fb-post-1"
    publishers = {Platform.FACEBOOK: fb, Platform.INSTAGRAM: MagicMock()}
    tools = build_publish_tools(
        repo=repo, publishers=publishers,
        publish_time_local="19:00", publish_timezone="Europe/Lisbon",
    )
    publish_due = next(t for t in tools if t.name == "publish_due_drafts")
    with freeze_time("2026-04-01 19:30:00"):
        result = publish_due.invoke({})
    assert "fb-post-1" in result
    fb.publish.assert_called_once()
    d = repo.get_draft(did)
    assert d is not None
    assert d.status == DraftStatus.PUBLISHED


def test_publish_due_drafts_publishes_post_now(repo: Repository, tmp_path: Path) -> None:
    img = tmp_path / "card.png"
    img.write_bytes(b"PNG")
    did = repo.create_draft(
        activity_id=1, platform=Platform.INSTAGRAM, language=Language.PT,
        caption="x", media_paths=str(img),
    )
    repo.set_approved(did, post_now=True)

    ig = MagicMock()
    ig.publish.return_value = "ig-post-1"
    publishers = {Platform.FACEBOOK: MagicMock(), Platform.INSTAGRAM: ig}
    tools = build_publish_tools(
        repo=repo, publishers=publishers,
        publish_time_local="19:00", publish_timezone="Europe/Lisbon",
    )
    publish_due = next(t for t in tools if t.name == "publish_due_drafts")
    publish_due.invoke({})
    ig.publish.assert_called_once()


def test_publish_to_facebook_refuses_unless_approved(repo: Repository) -> None:
    did = repo.create_draft(
        activity_id=1, platform=Platform.FACEBOOK, language=Language.PT, caption="x",
    )
    publishers = {Platform.FACEBOOK: MagicMock(), Platform.INSTAGRAM: MagicMock()}
    tools = build_publish_tools(
        repo=repo, publishers=publishers,
        publish_time_local="19:00", publish_timezone="Europe/Lisbon",
    )
    publish_fb = next(t for t in tools if t.name == "publish_to_facebook")
    result = publish_fb.invoke({"draft_id": did})
    assert "REJECTED" in result
