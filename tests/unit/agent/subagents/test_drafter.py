"""Tests for the drafter sub-agent definition."""

from __future__ import annotations

from langchain_anthropic import ChatAnthropic

from cycling_agent.agent.subagents.drafter import DRAFTER_NAME, build_drafter_subagent

_MODEL = "claude-sonnet-4-6"


def test_drafter_definition_has_required_keys() -> None:
    sub = build_drafter_subagent(model=_MODEL)
    assert sub["name"] == DRAFTER_NAME
    assert sub["description"]
    assert "draft" in sub["description"].lower()
    assert "system_prompt" in sub
    assert "self-critique" in sub["system_prompt"].lower() or "critique" in sub["system_prompt"].lower()


def test_drafter_prompt_mentions_sponsors_and_voice() -> None:
    sub = build_drafter_subagent(model=_MODEL)
    p = sub["system_prompt"].lower()
    assert "sponsor" in p
    assert "voice" in p or "style" in p
    assert "caption" in p


def test_drafter_binds_configured_model() -> None:
    sub = build_drafter_subagent(model=_MODEL)
    assert isinstance(sub["model"], ChatAnthropic)
    assert sub["model"].model == _MODEL
