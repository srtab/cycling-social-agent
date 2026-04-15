"""Drafter sub-agent definition for the deep-agent orchestrator."""

from __future__ import annotations

from cycling_agent.agent.prompts import load_prompt

DRAFTER_NAME = "drafter"


def build_drafter_subagent() -> dict:
    """Return the deepagents sub-agent dict for the drafter.

    Compatible with ``deepagents.create_deep_agent(subagents=[...])``.
    """
    return {
        "name": DRAFTER_NAME,
        "description": (
            "Use to draft a single social-media caption for one platform and one language. "
            "Pass all context in the description: platform, language, activity summary, "
            "feeling note, sponsor list, style examples, and any regenerate hint."
        ),
        "prompt": load_prompt("drafter"),
    }
