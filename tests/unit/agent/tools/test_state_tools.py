"""Tests for state-management tools."""

from __future__ import annotations

import datetime as dt

import pytest

from cycling_agent.agent.tools.state_tools import build_state_tools
from cycling_agent.db.engine import build_engine, build_session_factory, init_schema
from cycling_agent.db.models import ActivityStatus, DraftStatus, Language, Platform
from cycling_agent.db.repo import Repository


@pytest.fixture()
def repo() -> Repository:
    engine = build_engine(":memory:")
    init_schema(engine)
    repo = Repository(build_session_factory(engine))
    repo.upsert_activity(id=1, started_at=dt.datetime(2026, 4, 1), name="Crit", workout_type=11)
    return repo


def test_mark_processed_rejects_when_drafts_not_terminal(repo: Repository) -> None:
    repo.create_draft(activity_id=1, platform=Platform.FACEBOOK, language=Language.PT, caption="x")
    tools = build_state_tools(repo=repo)
    mark = next(t for t in tools if t.name == "mark_processed")
    result = mark.invoke({"activity_id": 1})
    assert "REJECTED" in result


def test_mark_processed_succeeds_when_all_terminal(repo: Repository) -> None:
    d1 = repo.create_draft(activity_id=1, platform=Platform.FACEBOOK, language=Language.PT, caption="x")
    d2 = repo.create_draft(activity_id=1, platform=Platform.INSTAGRAM, language=Language.PT, caption="y")
    repo.set_draft_status(d1, DraftStatus.PUBLISHED)
    repo.set_draft_status(d2, DraftStatus.REJECTED)
    tools = build_state_tools(repo=repo)
    mark = next(t for t in tools if t.name == "mark_processed")
    result = mark.invoke({"activity_id": 1})
    assert "processed" in result.lower()
    a = repo.get_activity(1)
    assert a is not None
    assert a.status == ActivityStatus.PROCESSED


def test_log_feedback_writes_event(repo: Repository) -> None:
    did = repo.create_draft(activity_id=1, platform=Platform.FACEBOOK, language=Language.PT, caption="x")
    tools = build_state_tools(repo=repo)
    log_fb = next(t for t in tools if t.name == "log_feedback")
    log_fb.invoke({"draft_id": did, "kind": "agent_note", "payload": '{"observation":"caption was rewritten 3 times"}'})
    events = repo.list_approval_events_for_draft(did)
    assert len(events) == 1
