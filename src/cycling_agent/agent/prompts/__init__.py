"""Prompt loader utilities."""

from __future__ import annotations

from pathlib import Path

PROMPT_DIR = Path(__file__).resolve().parent


def load_prompt(name: str, **substitutions: str) -> str:
    """Load a prompt markdown file. If ``substitutions`` are given, they are
    applied via ``str.format``; otherwise the raw text is returned so prompts
    without placeholders don't need to escape literal braces."""
    text = (PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8")
    if substitutions:
        text = text.format(**substitutions)
    return text
