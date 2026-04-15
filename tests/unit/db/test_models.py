"""Tests for the SQLAlchemy model layer."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from cycling_agent.db.engine import build_engine, build_session_factory, init_schema
from cycling_agent.db.models import (
    Activity,
    ActivityStatus,
    ApprovalEvent,
    Draft,
    DraftStatus,
    Language,
    Platform,
    Post,
    Sponsor,
    StyleExample,
)


def _session():
    engine = build_engine(":memory:")
    init_schema(engine)
    return build_session_factory(engine)()


def test_activity_default_status_is_detected() -> None:
    s = _session()
    a = Activity(id=1, started_at=dt.datetime(2026, 4, 1, 10, 0), name="Crit", workout_type=11)
    s.add(a)
    s.commit()
    assert a.status == ActivityStatus.DETECTED


def test_draft_unique_per_activity_platform_language() -> None:
    s = _session()
    s.add(Activity(id=1, started_at=dt.datetime(2026, 4, 1), name="r", workout_type=11))
    s.add(Draft(activity_id=1, platform=Platform.FACEBOOK, language=Language.PT, caption="x"))
    s.commit()
    s.add(Draft(activity_id=1, platform=Platform.FACEBOOK, language=Language.PT, caption="y"))
    with pytest.raises(IntegrityError):
        s.commit()


def test_draft_default_state_is_pending() -> None:
    s = _session()
    s.add(Activity(id=1, started_at=dt.datetime(2026, 4, 1), name="r", workout_type=11))
    d = Draft(activity_id=1, platform=Platform.INSTAGRAM, language=Language.EN, caption="x")
    s.add(d)
    s.commit()
    assert d.status == DraftStatus.PENDING
    assert d.post_now is False
    assert d.regenerate_count == 0


def test_post_links_to_draft() -> None:
    s = _session()
    s.add(Activity(id=1, started_at=dt.datetime(2026, 4, 1), name="r", workout_type=11))
    d = Draft(activity_id=1, platform=Platform.FACEBOOK, language=Language.PT, caption="x")
    s.add(d)
    s.commit()
    s.add(Post(draft_id=d.id, platform=Platform.FACEBOOK, external_post_id="123_456"))
    s.commit()
    fetched = s.execute(select(Post).where(Post.draft_id == d.id)).scalar_one()
    assert fetched.external_post_id == "123_456"


def test_sponsor_basic_create() -> None:
    s = _session()
    sponsor = Sponsor(name="BrandX", handle_facebook="@brandx", handle_instagram="@brandx", hashtag="#brandx")
    s.add(sponsor)
    s.commit()
    assert sponsor.id is not None


def test_style_example_per_language() -> None:
    s = _session()
    s.add(StyleExample(language=Language.PT, text="Dia duro mas feliz."))
    s.add(StyleExample(language=Language.EN, text="Hard day, happy ending."))
    s.commit()
    assert s.query(StyleExample).count() == 2


def test_approval_event_audit_trail() -> None:
    s = _session()
    s.add(Activity(id=1, started_at=dt.datetime(2026, 4, 1), name="r", workout_type=11))
    d = Draft(activity_id=1, platform=Platform.FACEBOOK, language=Language.PT, caption="x")
    s.add(d)
    s.commit()
    s.add(ApprovalEvent(draft_id=d.id, event="approved", payload="{}"))
    s.commit()
    assert s.query(ApprovalEvent).count() == 1
