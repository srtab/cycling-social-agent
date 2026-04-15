"""Reflector sub-agent: analyses approval feedback and proposes style updates."""

from __future__ import annotations

from cycling_agent.agent.prompts import load_prompt

REFLECTOR_NAME = "reflector"


def build_reflector_subagent() -> dict:
    return {
        "name": REFLECTOR_NAME,
        "description": (
            "Use to analyse recent approval_events (edits, regenerate hints, rejects) "
            "and propose a markdown diff of style-guide changes for the rider to apply manually."
        ),
        "prompt": load_prompt("reflector"),
    }
