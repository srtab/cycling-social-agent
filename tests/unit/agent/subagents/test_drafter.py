"""Tests for the drafter sub-agent definition."""

from __future__ import annotations

from cycling_agent.agent.subagents.drafter import DRAFTER_NAME, build_drafter_subagent


def test_drafter_definition_has_required_keys() -> None:
    sub = build_drafter_subagent()
    assert sub["name"] == DRAFTER_NAME
    assert sub["description"]
    assert "draft" in sub["description"].lower()
    assert "prompt" in sub
    assert "self-critique" in sub["prompt"].lower() or "critique" in sub["prompt"].lower()


def test_drafter_prompt_mentions_sponsors_and_voice() -> None:
    sub = build_drafter_subagent()
    p = sub["prompt"].lower()
    assert "sponsor" in p
    assert "voice" in p or "style" in p
    assert "caption" in p
