"""Tests for orchestrator construction.

We do not invoke the LLM in unit tests — that's covered in the smoke test (T24).
Here we only assert the orchestrator is built with the expected tools and sub-agents.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cycling_agent.agent.orchestrator import OrchestratorDeps, build_orchestrator
from cycling_agent.db.engine import build_engine, build_session_factory, init_schema
from cycling_agent.db.models import Platform
from cycling_agent.db.repo import Repository


@pytest.fixture()
def deps(tmp_path: Path) -> OrchestratorDeps:
    engine = build_engine(":memory:")
    init_schema(engine)
    repo = Repository(build_session_factory(engine))
    # These tests don't invoke tools, so a non-running loop is fine here —
    # it's only used by the approval-tool closure that ``_collect_tools`` bakes.
    loop = asyncio.new_event_loop()
    return OrchestratorDeps(
        repo=repo,
        strava_client=MagicMock(),
        strava_poller=MagicMock(),
        publishers={Platform.FACEBOOK: MagicMock(), Platform.INSTAGRAM: MagicMock()},
        approval_bot=MagicMock(),
        media_dir=tmp_path / "media",
        publish_time_local="19:00",
        publish_timezone="Europe/Lisbon",
        orchestrator_model="claude-haiku-4-5-20251001",
        drafter_model="claude-sonnet-4-6",
        reflector_model="claude-sonnet-4-6",
        main_loop=loop,
    )


def test_collect_tools_returns_expected_names(deps: OrchestratorDeps) -> None:
    from cycling_agent.agent.orchestrator import _collect_tools

    tools = _collect_tools(deps)
    names = {t.name for t in tools}
    assert {
        "list_new_races",
        "get_activity_detail",
        "get_feeling",
        "read_sponsors",
        "read_style_examples",
        "render_stats_card",
        "render_route_map",
        "send_for_approval",
        "check_approval_status",
        "schedule_publish",
        "publish_due_drafts",
        "publish_to_facebook",
        "publish_to_instagram",
        "mark_processed",
        "log_feedback",
        "list_drafts_for_activity",
    }.issubset(names)


def test_build_orchestrator_returns_agent(deps: OrchestratorDeps, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return MagicMock(name="fake-agent")

    monkeypatch.setattr("cycling_agent.agent.orchestrator.create_deep_agent", fake_create)
    agent = build_orchestrator(deps)

    assert agent is not None
    assert "tools" in captured
    assert "system_prompt" in captured
    assert "subagents" in captured
    # Default enabled_platforms includes both — the rendered prompt must
    # reflect that so the orchestrator generates drafts for each.
    assert "[(facebook, pt), (instagram, pt)]" in captured["system_prompt"]
    sub_names = {s["name"] for s in captured["subagents"]}
    assert {"drafter", "reflector"}.issubset(sub_names)
    # Each subagent must bind its own model — otherwise deepagents silently
    # falls back to the orchestrator's model.
    by_name = {s["name"]: s for s in captured["subagents"]}
    assert by_name["drafter"]["model"].model == deps.drafter_model
    assert by_name["reflector"]["model"].model == deps.reflector_model


def test_build_orchestrator_prompt_excludes_disabled_platform(
    deps: OrchestratorDeps, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return MagicMock(name="fake-agent")

    monkeypatch.setattr("cycling_agent.agent.orchestrator.create_deep_agent", fake_create)
    deps.enabled_platforms = {Platform.FACEBOOK}
    build_orchestrator(deps)

    prompt = captured["system_prompt"]
    assert "[(facebook, pt)]" in prompt
    assert "instagram" not in prompt
