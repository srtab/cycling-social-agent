"""Tests for the reflector sub-agent definition."""

from __future__ import annotations

from langchain_anthropic import ChatAnthropic

from cycling_agent.agent.subagents.reflector import REFLECTOR_NAME, build_reflector_subagent

_MODEL = "claude-sonnet-4-6"


def test_reflector_definition_has_required_keys() -> None:
    sub = build_reflector_subagent(model=_MODEL)
    assert sub["name"] == REFLECTOR_NAME
    assert "reflect" in sub["description"].lower() or "feedback" in sub["description"].lower()
    assert "system_prompt" in sub


def test_reflector_prompt_mentions_diff_output() -> None:
    sub = build_reflector_subagent(model=_MODEL)
    p = sub["system_prompt"]
    assert "ADD" in p or "add" in p
    assert "REMOVE" in p or "remove" in p
    assert "diff" in p.lower() or "proposal" in p.lower()


def test_reflector_binds_configured_model() -> None:
    sub = build_reflector_subagent(model=_MODEL)
    assert isinstance(sub["model"], ChatAnthropic)
    assert sub["model"].model == _MODEL
