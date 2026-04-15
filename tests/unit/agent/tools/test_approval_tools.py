"""Tests for approval tools (send_for_approval + check_approval_status)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from cycling_agent.agent.tools.approval_tools import build_approval_tools
from cycling_agent.db.engine import build_engine, build_session_factory, init_schema
from cycling_agent.db.models import DraftStatus, Language, Platform, Sponsor
from cycling_agent.db.repo import Repository


@pytest.fixture()
def repo() -> Repository:
    engine = build_engine(":memory:")
    init_schema(engine)
    repo = Repository(build_session_factory(engine))
    repo.upsert_activity(id=1, started_at=dt.datetime(2026, 4, 1), name="Crit", workout_type=11)
    repo.replace_sponsors(
        [
            Sponsor(name="BrandX", handle_facebook="@brandx", handle_instagram="@brandx", hashtag="#brandx"),
            Sponsor(name="BrandY", handle_facebook="@brandy", handle_instagram="@brandy", hashtag="#brandy"),
        ]
    )
    return repo


@pytest.fixture()
def fake_bot() -> MagicMock:
    bot = MagicMock()
    bot.send_draft_card = AsyncMock(return_value=4242)
    return bot


def test_send_for_approval_rejects_when_sponsor_missing(repo: Repository, fake_bot: MagicMock, tmp_path: Path) -> None:
    img = tmp_path / "card.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 50)

    tools = build_approval_tools(repo=repo, bot=fake_bot)
    send_for_approval = next(t for t in tools if t.name == "send_for_approval")

    result = send_for_approval.invoke(
        {
            "activity_id": 1,
            "platform": "facebook",
            "language": "pt",
            "caption": "Hello, mentions only @brandx #brandx",  # missing @brandy #brandy
            "hashtags": "",
            "media_paths": str(img),
        }
    )
    assert "missing" in result.lower()
    fake_bot.send_draft_card.assert_not_called()


def test_send_for_approval_creates_draft_and_sends(repo: Repository, fake_bot: MagicMock, tmp_path: Path) -> None:
    img = tmp_path / "card.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 50)

    caption = "Hello @brandx @brandy #brandx #brandy"
    tools = build_approval_tools(repo=repo, bot=fake_bot)
    send_for_approval = next(t for t in tools if t.name == "send_for_approval")
    result = send_for_approval.invoke(
        {
            "activity_id": 1,
            "platform": "facebook",
            "language": "pt",
            "caption": caption,
            "hashtags": "",
            "media_paths": str(img),
        }
    )
    assert "Sent" in result
    fake_bot.send_draft_card.assert_awaited_once()

    drafts = repo.list_drafts_in_states([DraftStatus.AWAITING_APPROVAL])
    assert len(drafts) == 1
    assert drafts[0].telegram_message_id == 4242


def test_check_approval_status_returns_pending(repo: Repository, fake_bot: MagicMock) -> None:
    did = repo.create_draft(
        activity_id=1,
        platform=Platform.FACEBOOK,
        language=Language.PT,
        caption="x",
    )
    repo.set_draft_status(did, DraftStatus.AWAITING_APPROVAL, telegram_message_id=42)
    tools = build_approval_tools(repo=repo, bot=fake_bot)
    check = next(t for t in tools if t.name == "check_approval_status")
    result = check.invoke({"draft_id": did})
    assert "pending" in result.lower()


def test_check_approval_status_returns_approved_with_post_now(repo: Repository, fake_bot: MagicMock) -> None:
    did = repo.create_draft(
        activity_id=1,
        platform=Platform.FACEBOOK,
        language=Language.PT,
        caption="x",
    )
    repo.set_approved(did, post_now=True)
    tools = build_approval_tools(repo=repo, bot=fake_bot)
    check = next(t for t in tools if t.name == "check_approval_status")
    result = check.invoke({"draft_id": did})
    assert "approved" in result.lower()
    assert "post_now=true" in result.lower()


def test_check_approval_status_returns_regenerate_hint(repo: Repository, fake_bot: MagicMock) -> None:
    did = repo.create_draft(
        activity_id=1,
        platform=Platform.FACEBOOK,
        language=Language.PT,
        caption="x",
    )
    repo.set_draft_status(did, DraftStatus.REGENERATING, feedback_hint="more grateful")
    tools = build_approval_tools(repo=repo, bot=fake_bot)
    check = next(t for t in tools if t.name == "check_approval_status")
    result = check.invoke({"draft_id": did})
    assert "regenerate" in result.lower()
    assert "more grateful" in result
