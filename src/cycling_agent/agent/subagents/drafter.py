"""Drafter sub-agent definition for the deep-agent orchestrator."""

from __future__ import annotations

from langchain_anthropic import ChatAnthropic

from cycling_agent.agent.prompts import load_prompt

DRAFTER_NAME = "drafter"


def build_drafter_subagent(*, model: str) -> dict:
    """Return the deepagents sub-agent dict for the drafter.

    Compatible with ``deepagents.create_deep_agent(subagents=[...])``.
    Without an explicit ``"model"`` key, deepagents would fall back to the
    orchestrator's model — so we bind the drafter's configured model here.
    """
    return {
        "name": DRAFTER_NAME,
        "description": (
            "Use to draft a single social-media caption for one platform and one language. "
            "Pass all context in the description: platform, language, activity summary, "
            "feeling note, sponsor list, style examples, and any regenerate hint."
        ),
        "system_prompt": load_prompt("drafter"),
        "model": ChatAnthropic(model=model, max_tokens=4096, temperature=0.4),
    }
