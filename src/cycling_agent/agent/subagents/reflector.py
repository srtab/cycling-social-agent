"""Reflector sub-agent: analyses approval feedback and proposes style updates."""

from __future__ import annotations

from langchain_anthropic import ChatAnthropic

from cycling_agent.agent.prompts import load_prompt

REFLECTOR_NAME = "reflector"


def build_reflector_subagent(*, model: str) -> dict:
    """Return the deepagents sub-agent dict for the reflector.

    Without an explicit ``"model"`` key, deepagents would fall back to the
    orchestrator's model — so we bind the reflector's configured model here.
    """
    return {
        "name": REFLECTOR_NAME,
        "description": (
            "Use to reflect on recent approval feedback (edits, regenerate hints, rejects) "
            "and propose a markdown diff of style-guide changes for the rider to apply manually."
        ),
        "system_prompt": load_prompt("reflector"),
        "model": ChatAnthropic(model=model, max_tokens=4096),
    }
