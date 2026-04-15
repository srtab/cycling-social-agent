"""Tests for approval tools (send_for_approval + check_approval_status)."""

from __future__ import annotations

import asyncio
import datetime as dt
import threading
from collections.abc import Iterator
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
def running_loop() -> Iterator[asyncio.AbstractEventLoop]:
    """A real asyncio loop running in a background thread.

    Mirrors production: ``send_for_approval`` is called from a worker thread
    (``asyncio.to_thread`` in the agent runner) and must schedule its
    coroutine on the main loop. A MagicMock can't exercise that path.
    """
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    try:
        yield loop
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=2)
        loop.close()


@pytest.fixture()
def fake_bot() -> MagicMock:
    bot = MagicMock()
    bot.send_draft_card = AsyncMock(return_value=4242)
    return bot


def test_send_for_approval_rejects_when_sponsor_missing(
    repo: Repository, fake_bot: MagicMock, running_loop: asyncio.AbstractEventLoop, tmp_path: Path
) -> None:
    img = tmp_path / "card.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 50)

    tools = build_approval_tools(repo=repo, bot=fake_bot, main_loop=running_loop)
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


def test_send_for_approval_creates_draft_and_sends(
    repo: Repository, fake_bot: MagicMock, running_loop: asyncio.AbstractEventLoop, tmp_path: Path
) -> None:
    img = tmp_path / "card.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 50)

    caption = "Hello @brandx @brandy #brandx #brandy"
    tools = build_approval_tools(repo=repo, bot=fake_bot, main_loop=running_loop)
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


def test_check_approval_status_returns_pending(
    repo: Repository, fake_bot: MagicMock, running_loop: asyncio.AbstractEventLoop
) -> None:
    did = repo.create_draft(
        activity_id=1,
        platform=Platform.FACEBOOK,
        language=Language.PT,
        caption="x",
    )
    repo.set_draft_status(did, DraftStatus.AWAITING_APPROVAL, telegram_message_id=42)
    tools = build_approval_tools(repo=repo, bot=fake_bot, main_loop=running_loop)
    check = next(t for t in tools if t.name == "check_approval_status")
    result = check.invoke({"draft_id": did})
    assert "pending" in result.lower()


def test_check_approval_status_returns_approved_with_post_now(
    repo: Repository, fake_bot: MagicMock, running_loop: asyncio.AbstractEventLoop
) -> None:
    did = repo.create_draft(
        activity_id=1,
        platform=Platform.FACEBOOK,
        language=Language.PT,
        caption="x",
    )
    repo.set_approved(did, post_now=True)
    tools = build_approval_tools(repo=repo, bot=fake_bot, main_loop=running_loop)
    check = next(t for t in tools if t.name == "check_approval_status")
    result = check.invoke({"draft_id": did})
    assert "approved" in result.lower()
    assert "post_now=true" in result.lower()


def test_send_for_approval_gracefully_rejects_duplicate(
    repo: Repository, fake_bot: MagicMock, running_loop: asyncio.AbstractEventLoop, tmp_path: Path
) -> None:
    """A duplicate (activity, platform, language) must NOT crash the tick.

    Why: the orchestrator has historically double-inserted when its state check
    is wrong. A crash in this tool takes down the whole invocation; a REJECTED
    string lets the agent recover and move on.
    """
    img = tmp_path / "card.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 50)

    # Pre-existing awaiting-approval draft for (activity=1, facebook, pt).
    existing_id = repo.create_draft(activity_id=1, platform=Platform.FACEBOOK, language=Language.PT, caption="existing")
    repo.set_draft_status(existing_id, DraftStatus.AWAITING_APPROVAL, telegram_message_id=1)

    tools = build_approval_tools(repo=repo, bot=fake_bot, main_loop=running_loop)
    send_for_approval = next(t for t in tools if t.name == "send_for_approval")
    result = send_for_approval.invoke(
        {
            "activity_id": 1,
            "platform": "facebook",
            "language": "pt",
            "caption": "Hello @brandx @brandy #brandx #brandy",
            "hashtags": "",
            "media_paths": str(img),
        }
    )
    assert "REJECTED" in result
    assert "already exists" in result.lower()
    # The previous draft's telegram card must not be re-sent.
    fake_bot.send_draft_card.assert_not_called()


def test_check_approval_status_returns_regenerate_hint(
    repo: Repository, fake_bot: MagicMock, running_loop: asyncio.AbstractEventLoop
) -> None:
    did = repo.create_draft(
        activity_id=1,
        platform=Platform.FACEBOOK,
        language=Language.PT,
        caption="x",
    )
    repo.set_draft_status(did, DraftStatus.REGENERATING, feedback_hint="more grateful")
    tools = build_approval_tools(repo=repo, bot=fake_bot, main_loop=running_loop)
    check = next(t for t in tools if t.name == "check_approval_status")
    result = check.invoke({"draft_id": did})
    assert "regenerate" in result.lower()
    assert "more grateful" in result


def test_send_for_approval_runs_coroutine_on_main_loop(
    repo: Repository, running_loop: asyncio.AbstractEventLoop, tmp_path: Path
) -> None:
    """Regression: the coroutine must run on the provided main loop, not a throwaway one.

    Why this matters: the tool is invoked from ``asyncio.to_thread`` in the agent
    runner, so the worker thread has no loop of its own. Using ``asyncio.run``
    spins up a one-shot loop and leaves orphaned httpx connections bound to it
    in the shared Telegram ``Bot``'s connection pool. Later, when Telegram
    button callbacks run on the main loop, httpx tries to evict those stale
    connections and crashes with ``RuntimeError: Event loop is closed``.

    This test calls the tool from the pytest main thread (which has no running
    loop), so the fix's ``run_coroutine_threadsafe`` must target ``main_loop``
    for the coroutine to execute at all — and we additionally verify that the
    loop observed inside the coroutine *is* the fixture's loop.
    """
    img = tmp_path / "card.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 50)

    observed: dict[str, int] = {}

    async def fake_send_draft_card(*, draft_id: int, caption: str, media_paths: list[Path]) -> int:
        observed["loop_id"] = id(asyncio.get_running_loop())
        return 4242

    bot = MagicMock()
    bot.send_draft_card = fake_send_draft_card

    tools = build_approval_tools(repo=repo, bot=bot, main_loop=running_loop)
    send_for_approval = next(t for t in tools if t.name == "send_for_approval")

    result = send_for_approval.invoke(
        {
            "activity_id": 1,
            "platform": "facebook",
            "language": "pt",
            "caption": "Hello @brandx @brandy #brandx #brandy",
            "hashtags": "",
            "media_paths": str(img),
        }
    )

    assert "Sent" in result
    assert observed["loop_id"] == id(running_loop)
