"""Tests for the reflector sub-agent definition."""

from __future__ import annotations

from cycling_agent.agent.subagents.reflector import REFLECTOR_NAME, build_reflector_subagent


def test_reflector_definition_has_required_keys() -> None:
    sub = build_reflector_subagent()
    assert sub["name"] == REFLECTOR_NAME
    assert "reflect" in sub["description"].lower() or "feedback" in sub["description"].lower()
    assert "prompt" in sub


def test_reflector_prompt_mentions_diff_output() -> None:
    sub = build_reflector_subagent()
    p = sub["prompt"]
    assert "ADD" in p or "add" in p
    assert "REMOVE" in p or "remove" in p
    assert "diff" in p.lower() or "proposal" in p.lower()
