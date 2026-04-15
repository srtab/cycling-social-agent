"""Tests for the Telegram approval bot handlers."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from cycling_agent.approval.bot import (
    CB_APPROVE_NOW,
    CB_APPROVE_QUEUED,
    CB_REGENERATE,
    CB_REJECT,
    CB_RESCHEDULE,
    ApprovalBot,
    callback_data,
)
from cycling_agent.db.engine import build_engine, build_session_factory, init_schema
from cycling_agent.db.models import DraftStatus, Language, Platform
from cycling_agent.db.repo import Repository


@pytest.fixture()
def repo() -> Repository:
    engine = build_engine(":memory:")
    init_schema(engine)
    return Repository(build_session_factory(engine))


@pytest.fixture()
def seeded_draft(repo: Repository) -> int:
    repo.upsert_activity(id=1, started_at=dt.datetime(2026, 4, 1), name="Crit", workout_type=11)
    return repo.create_draft(
        activity_id=1,
        platform=Platform.FACEBOOK,
        language=Language.PT,
        caption="hello",
        hashtags=None,
        media_paths=None,
    )


def _query(callback_data_str: str) -> SimpleNamespace:
    """Build a minimal PTB CallbackQuery stub."""
    msg = SimpleNamespace(message_id=42, chat_id=11111)
    answer = AsyncMock()
    return SimpleNamespace(
        data=callback_data_str,
        answer=answer,
        message=msg,
        from_user=SimpleNamespace(id=11111),
        edit_message_reply_markup=AsyncMock(),
    )


def _update(query) -> SimpleNamespace:
    return SimpleNamespace(callback_query=query, effective_chat=SimpleNamespace(id=11111))


def _context() -> SimpleNamespace:
    bot = MagicMock()
    bot.send_message = AsyncMock()
    return SimpleNamespace(bot=bot, user_data={}, chat_data={})


async def test_callback_data_helpers_roundtrip() -> None:
    payload = callback_data(CB_APPROVE_QUEUED, draft_id=42)
    bot = ApprovalBot(repo=MagicMock(), chat_id=1)
    parsed = bot._parse_callback(payload)
    assert parsed == (CB_APPROVE_QUEUED, 42)


async def test_handle_approve_queued_sets_status(repo: Repository, seeded_draft: int) -> None:
    bot = ApprovalBot(repo=repo, chat_id=11111)
    update = _update(_query(callback_data(CB_APPROVE_QUEUED, draft_id=seeded_draft)))
    await bot.handle_callback(update, _context())
    d = repo.get_draft(seeded_draft)
    assert d is not None
    assert d.status == DraftStatus.APPROVED
    assert d.post_now is False


async def test_handle_approve_now_sets_post_now(repo: Repository, seeded_draft: int) -> None:
    bot = ApprovalBot(repo=repo, chat_id=11111)
    update = _update(_query(callback_data(CB_APPROVE_NOW, draft_id=seeded_draft)))
    await bot.handle_callback(update, _context())
    d = repo.get_draft(seeded_draft)
    assert d is not None
    assert d.status == DraftStatus.APPROVED
    assert d.post_now is True


async def test_handle_reject_marks_rejected(repo: Repository, seeded_draft: int) -> None:
    bot = ApprovalBot(repo=repo, chat_id=11111)
    update = _update(_query(callback_data(CB_REJECT, draft_id=seeded_draft)))
    await bot.handle_callback(update, _context())
    d = repo.get_draft(seeded_draft)
    assert d is not None
    assert d.status == DraftStatus.REJECTED


async def test_handle_regenerate_prompts_for_hint(repo: Repository, seeded_draft: int) -> None:
    bot = ApprovalBot(repo=repo, chat_id=11111)
    update = _update(_query(callback_data(CB_REGENERATE, draft_id=seeded_draft)))
    ctx = _context()
    await bot.handle_callback(update, ctx)
    d = repo.get_draft(seeded_draft)
    assert d is not None
    assert d.status == DraftStatus.REGENERATING
    ctx.bot.send_message.assert_awaited()
    assert ctx.user_data.get("awaiting_hint_for") == seeded_draft


async def test_handle_text_message_after_regenerate_records_hint(repo: Repository, seeded_draft: int) -> None:
    bot = ApprovalBot(repo=repo, chat_id=11111)
    repo.set_draft_status(seeded_draft, DraftStatus.REGENERATING)

    ctx = _context()
    ctx.user_data["awaiting_hint_for"] = seeded_draft
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=11111),
        message=SimpleNamespace(text="more grateful, less hype", reply_text=AsyncMock()),
    )
    await bot.handle_text(update, ctx)

    d = repo.get_draft(seeded_draft)
    assert d is not None
    assert d.feedback_hint == "more grateful, less hype"
    assert "awaiting_hint_for" not in ctx.user_data


async def test_handle_reschedule_prompts_for_time(repo: Repository, seeded_draft: int) -> None:
    repo.set_approved(seeded_draft, post_now=False)
    repo.schedule_draft(seeded_draft, dt.datetime(2026, 4, 1, 19, 0))
    bot = ApprovalBot(repo=repo, chat_id=11111)
    update = _update(_query(callback_data(CB_RESCHEDULE, draft_id=seeded_draft)))
    ctx = _context()
    await bot.handle_callback(update, ctx)
    assert ctx.user_data.get("awaiting_reschedule_for") == seeded_draft
    ctx.bot.send_message.assert_awaited()


async def test_handle_text_after_reschedule_updates_scheduled_for(repo: Repository, seeded_draft: int) -> None:
    repo.set_approved(seeded_draft, post_now=False)
    repo.schedule_draft(seeded_draft, dt.datetime(2026, 4, 1, 19, 0))
    bot = ApprovalBot(repo=repo, chat_id=11111)
    ctx = _context()
    ctx.user_data["awaiting_reschedule_for"] = seeded_draft
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=11111),
        message=SimpleNamespace(text="2026-04-02 21:00", reply_text=AsyncMock()),
    )
    await bot.handle_text(update, ctx)
    d = repo.get_draft(seeded_draft)
    assert d is not None
    assert d.scheduled_for == dt.datetime(2026, 4, 2, 21, 0)


async def test_handle_callback_ignores_other_chats(repo: Repository, seeded_draft: int) -> None:
    bot = ApprovalBot(repo=repo, chat_id=99999)
    update = SimpleNamespace(
        callback_query=_query(callback_data(CB_APPROVE_QUEUED, draft_id=seeded_draft)),
        effective_chat=SimpleNamespace(id=11111),
    )
    await bot.handle_callback(update, _context())
    d = repo.get_draft(seeded_draft)
    assert d is not None
    assert d.status != DraftStatus.APPROVED


async def test_send_draft_card_calls_telegram_with_buttons(repo: Repository, seeded_draft: int, tmp_path: Path) -> None:
    img = tmp_path / "card.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 50)

    fake_bot = MagicMock()
    fake_bot.send_photo = AsyncMock(return_value=SimpleNamespace(message_id=4242))
    bot = ApprovalBot(repo=repo, chat_id=11111, telegram_bot=fake_bot)

    msg_id = await bot.send_draft_card(draft_id=seeded_draft, caption="hello", media_paths=[img])
    assert msg_id == 4242
    fake_bot.send_photo.assert_awaited_once()
    kwargs = fake_bot.send_photo.await_args.kwargs
    assert kwargs["chat_id"] == 11111
    assert "reply_markup" in kwargs
