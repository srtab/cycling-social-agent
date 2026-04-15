"""Agent runner: invokes the orchestrator on a fixed interval.

- Records each invocation as an ``AgentRun`` row for observability.
- Caps tool-call recursion via langgraph ``recursion_limit`` (spec §10).
- Tracks consecutive failures and alerts the rider via Telegram after a
  configurable threshold (spec §11).
- Designed to share an asyncio event loop with the Telegram bot.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from typing import Any

import structlog

from cycling_agent.db.models import AgentRun
from cycling_agent.db.repo import Repository

log = structlog.get_logger(__name__)


class AgentRunner:
    def __init__(
        self,
        *,
        orchestrator: Any,
        repo: Repository,
        interval_seconds: float = 600,
        recursion_limit: int = 30,
        approval_bot: Any | None = None,
        failure_alert_threshold: int = 5,
    ) -> None:
        self._orchestrator = orchestrator
        self._repo = repo
        self._interval = interval_seconds
        self._recursion_limit = recursion_limit
        self._bot = approval_bot
        self._failure_threshold = failure_alert_threshold
        self._consecutive_failures = 0

    async def run_once(self) -> str:
        """Invoke the orchestrator one time and record the outcome."""
        run = AgentRun(started_at=dt.datetime.now(dt.UTC))
        with self._repo._session_factory() as s:
            s.add(run)
            s.commit()
            run_id = run.id

        try:
            # The orchestrator is sync (LangGraph compiled graph). Run in a thread
            # so it does not block the event loop (Telegram bot, etc).
            result = await asyncio.to_thread(
                self._orchestrator.invoke,
                {"messages": [{"role": "user", "content": "Process new race activities."}]},
                config={"recursion_limit": self._recursion_limit},
            )
            messages = result.get("messages", [])
            outcome_text = messages[-1].content if messages else "ok"
            outcome_summary = "ok"
            error_text: str | None = None
            self._consecutive_failures = 0
            log.info("agent.run.complete", run_id=run_id, summary=outcome_text[:200])
        except Exception as e:
            outcome_text = f"error: {e}"
            outcome_summary = "error"
            error_text = str(e)
            self._consecutive_failures += 1
            log.error("agent.run.failed", run_id=run_id, error=str(e), exc_info=True)
            if self._consecutive_failures >= self._failure_threshold:
                await self._maybe_alert(self._consecutive_failures, str(e))

        with self._repo._session_factory() as s:
            row = s.get(AgentRun, run_id)
            if row is not None:
                row.finished_at = dt.datetime.now(dt.UTC)
                row.outcome = outcome_summary
                row.error_text = error_text
                s.commit()

        return outcome_text

    async def run_forever(self, *, stop_event: asyncio.Event) -> None:
        """Run the orchestrator on a fixed interval until ``stop_event`` is set."""
        while not stop_event.is_set():
            await self.run_once()
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=self._interval)
            except TimeoutError:
                continue

    async def _maybe_alert(self, count: int, error: str) -> None:
        if self._bot is None or self._bot._bot is None or not self._bot._chat_id:
            return
        try:
            await self._bot._bot.send_message(
                chat_id=self._bot._chat_id,
                text=f"⚠️ cycling-agent: {count} consecutive failures. Last error: {error[:300]}",
            )
        except Exception as e:
            log.error("agent.alert.send_failed", error=str(e))
