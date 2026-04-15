"""Tests for the repository façade over the ORM."""

from __future__ import annotations

import datetime as dt

import pytest

from cycling_agent.db.engine import build_engine, build_session_factory, init_schema
from cycling_agent.db.models import ActivityStatus, DraftStatus, Language, Platform
from cycling_agent.db.repo import Repository


@pytest.fixture()
def repo() -> Repository:
    engine = build_engine(":memory:")
    init_schema(engine)
    return Repository(build_session_factory(engine))


def test_upsert_activity_inserts_new(repo: Repository) -> None:
    repo.upsert_activity(id=1, started_at=dt.datetime(2026, 4, 1), name="Crit", workout_type=11)
    activities = repo.list_activities_in_states([ActivityStatus.DETECTED])
    assert len(activities) == 1


def test_upsert_activity_idempotent(repo: Repository) -> None:
    repo.upsert_activity(id=1, started_at=dt.datetime(2026, 4, 1), name="Crit", workout_type=11)
    repo.upsert_activity(id=1, started_at=dt.datetime(2026, 4, 1), name="Crit", workout_type=11)
    assert len(repo.list_activities_in_states([ActivityStatus.DETECTED])) == 1


def test_set_feeling_text(repo: Repository) -> None:
    repo.upsert_activity(id=1, started_at=dt.datetime(2026, 4, 1), name="Crit", workout_type=11)
    repo.set_feeling_text(activity_id=1, text="rainy crit, top 20")
    a = repo.get_activity(1)
    assert a is not None
    assert a.feeling_text == "rainy crit, top 20"


def test_create_draft_returns_id(repo: Repository) -> None:
    repo.upsert_activity(id=1, started_at=dt.datetime(2026, 4, 1), name="Crit", workout_type=11)
    draft_id = repo.create_draft(
        activity_id=1, platform=Platform.FACEBOOK, language=Language.PT,
        caption="hello", hashtags="#x", media_paths="/tmp/a.png",
    )
    assert draft_id > 0
    d = repo.get_draft(draft_id)
    assert d is not None
    assert d.status == DraftStatus.DRAFTED  # repo upgrades from PENDING -> DRAFTED on create


def test_set_draft_status(repo: Repository) -> None:
    repo.upsert_activity(id=1, started_at=dt.datetime(2026, 4, 1), name="Crit", workout_type=11)
    did = repo.create_draft(activity_id=1, platform=Platform.FACEBOOK, language=Language.PT, caption="x")
    repo.set_draft_status(did, DraftStatus.AWAITING_APPROVAL, telegram_message_id=42)
    d = repo.get_draft(did)
    assert d is not None
    assert d.status == DraftStatus.AWAITING_APPROVAL
    assert d.telegram_message_id == 42


def test_find_due_drafts_returns_scheduled_past(repo: Repository) -> None:
    repo.upsert_activity(id=1, started_at=dt.datetime(2026, 4, 1), name="Crit", workout_type=11)
    did = repo.create_draft(activity_id=1, platform=Platform.FACEBOOK, language=Language.PT, caption="x")
    repo.set_approved(did, post_now=False)
    past = dt.datetime.now(dt.UTC) - dt.timedelta(minutes=5)
    repo.schedule_draft(did, past.replace(tzinfo=None))
    due = repo.find_due_drafts(now=dt.datetime.now(dt.UTC))
    assert [d.id for d in due] == [did]


def test_find_due_drafts_includes_post_now_approved(repo: Repository) -> None:
    repo.upsert_activity(id=1, started_at=dt.datetime(2026, 4, 1), name="Crit", workout_type=11)
    did = repo.create_draft(activity_id=1, platform=Platform.FACEBOOK, language=Language.PT, caption="x")
    repo.set_approved(did, post_now=True)
    due = repo.find_due_drafts(now=dt.datetime.now(dt.UTC))
    assert [d.id for d in due] == [did]


def test_record_post_marks_published(repo: Repository) -> None:
    repo.upsert_activity(id=1, started_at=dt.datetime(2026, 4, 1), name="Crit", workout_type=11)
    did = repo.create_draft(activity_id=1, platform=Platform.FACEBOOK, language=Language.PT, caption="x")
    repo.set_approved(did, post_now=True)
    repo.record_post(draft_id=did, platform=Platform.FACEBOOK, external_post_id="abc")
    d = repo.get_draft(did)
    assert d is not None
    assert d.status == DraftStatus.PUBLISHED


def test_mark_processed_requires_all_terminal(repo: Repository) -> None:
    repo.upsert_activity(id=1, started_at=dt.datetime(2026, 4, 1), name="Crit", workout_type=11)
    d1 = repo.create_draft(activity_id=1, platform=Platform.FACEBOOK, language=Language.PT, caption="x")
    repo.create_draft(activity_id=1, platform=Platform.INSTAGRAM, language=Language.PT, caption="y")
    repo.set_approved(d1, post_now=True)
    repo.record_post(draft_id=d1, platform=Platform.FACEBOOK, external_post_id="abc")
    # second draft still in DRAFTED
    with pytest.raises(ValueError, match="not all drafts terminal"):
        repo.mark_processed(activity_id=1)


def test_log_approval_event(repo: Repository) -> None:
    repo.upsert_activity(id=1, started_at=dt.datetime(2026, 4, 1), name="Crit", workout_type=11)
    did = repo.create_draft(activity_id=1, platform=Platform.FACEBOOK, language=Language.PT, caption="x")
    repo.log_approval_event(draft_id=did, event="approved", payload='{"post_now": false}')
    events = repo.list_approval_events_for_draft(did)
    assert len(events) == 1
    assert events[0].event == "approved"
