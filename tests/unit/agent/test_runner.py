"""Tests for the agent runner (scheduler-driven invocation)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from cycling_agent.agent.runner import AgentRunner
from cycling_agent.db.engine import build_engine, build_session_factory, init_schema
from cycling_agent.db.repo import Repository


@pytest.fixture()
def repo() -> Repository:
    engine = build_engine(":memory:")
    init_schema(engine)
    return Repository(build_session_factory(engine))


async def test_run_once_invokes_orchestrator(repo: Repository) -> None:
    fake_agent = MagicMock()
    fake_agent.invoke.return_value = {"messages": [MagicMock(content="processed activity 1")]}
    runner = AgentRunner(orchestrator=fake_agent, repo=repo)
    outcome = await runner.run_once()
    assert "processed" in outcome.lower()
    fake_agent.invoke.assert_called_once()


async def test_run_once_records_agent_run(repo: Repository) -> None:
    fake_agent = MagicMock()
    fake_agent.invoke.return_value = {"messages": [MagicMock(content="ok")]}
    runner = AgentRunner(orchestrator=fake_agent, repo=repo)
    await runner.run_once()

    from sqlalchemy import select

    from cycling_agent.db.models import AgentRun

    with repo._session_factory() as s:
        runs = list(s.execute(select(AgentRun)).scalars().all())
        assert len(runs) == 1
        assert runs[0].outcome == "ok"


async def test_run_once_records_failure(repo: Repository) -> None:
    fake_agent = MagicMock()
    fake_agent.invoke.side_effect = RuntimeError("boom")
    runner = AgentRunner(orchestrator=fake_agent, repo=repo)
    outcome = await runner.run_once()
    assert "error" in outcome.lower()

    from sqlalchemy import select

    from cycling_agent.db.models import AgentRun

    with repo._session_factory() as s:
        runs = list(s.execute(select(AgentRun)).scalars().all())
        assert runs[-1].outcome == "error"
        assert "boom" in (runs[-1].error_text or "")


async def test_run_forever_stops_on_event(repo: Repository) -> None:
    fake_agent = MagicMock()
    fake_agent.invoke.return_value = {"messages": [MagicMock(content="ok")]}
    runner = AgentRunner(orchestrator=fake_agent, repo=repo, interval_seconds=0.01)

    stop = asyncio.Event()
    task = asyncio.create_task(runner.run_forever(stop_event=stop))
    await asyncio.sleep(0.05)
    stop.set()
    await task

    assert fake_agent.invoke.call_count >= 2


async def test_run_once_passes_recursion_limit(repo: Repository) -> None:
    fake_agent = MagicMock()
    fake_agent.invoke.return_value = {"messages": [MagicMock(content="ok")]}
    runner = AgentRunner(orchestrator=fake_agent, repo=repo, recursion_limit=42)
    await runner.run_once()
    config = fake_agent.invoke.call_args.kwargs.get("config", {})
    assert config.get("recursion_limit") == 42


async def test_consecutive_failures_trigger_bot_alert(repo: Repository) -> None:
    fake_agent = MagicMock()
    fake_agent.invoke.side_effect = RuntimeError("boom")

    fake_bot = MagicMock()

    async def _send_card(*args, **kwargs):
        return 1

    fake_bot.send_draft_card = AsyncMock(side_effect=_send_card)
    fake_bot._chat_id = 1
    fake_bot._bot = MagicMock()
    fake_bot._bot.send_message = AsyncMock()

    runner = AgentRunner(
        orchestrator=fake_agent,
        repo=repo,
        approval_bot=fake_bot,
        failure_alert_threshold=3,
    )
    for _ in range(3):
        await runner.run_once()
    fake_bot._bot.send_message.assert_awaited()
    text = fake_bot._bot.send_message.await_args.kwargs.get("text", "")
    assert "3" in text and "fail" in text.lower()


async def test_success_resets_failure_counter(repo: Repository) -> None:
    fake_agent = MagicMock()
    fake_agent.invoke.side_effect = [
        RuntimeError("boom"),
        RuntimeError("boom"),
        {"messages": [MagicMock(content="ok")]},
        RuntimeError("boom"),
    ]

    fake_bot = MagicMock()
    fake_bot._chat_id = 1
    fake_bot._bot = MagicMock()
    fake_bot._bot.send_message = AsyncMock()

    runner = AgentRunner(
        orchestrator=fake_agent,
        repo=repo,
        approval_bot=fake_bot,
        failure_alert_threshold=3,
    )
    for _ in range(4):
        await runner.run_once()

    # 2 failures, 1 success (counter resets), 1 failure → never hits threshold
    fake_bot._bot.send_message.assert_not_awaited()
