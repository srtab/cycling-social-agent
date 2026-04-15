"""Sponsor and style-example tools."""

from __future__ import annotations

from langchain_core.tools import BaseTool, tool

from cycling_agent.db.models import Language
from cycling_agent.db.repo import Repository


def build_content_tools(*, repo: Repository) -> list[BaseTool]:
    @tool
    def read_sponsors() -> str:
        """Return the active sponsor list. All sponsors must be mentioned in every post."""
        sponsors = repo.list_sponsors()
        if not sponsors:
            return "No sponsors configured."
        lines = []
        for s in sponsors:
            line = f"- {s.name}"
            if s.hashtag:
                line += f" hashtag={s.hashtag}"
            if s.handle_facebook:
                line += f" fb={s.handle_facebook}"
            if s.handle_instagram:
                line += f" ig={s.handle_instagram}"
            lines.append(line)
        return "\n".join(lines)

    @tool
    def read_style_examples(language: str) -> str:
        """Return the rider's past posts to use as voice/few-shot examples.

        ``language`` must be 'pt'.
        """
        try:
            lang = Language(language)
        except ValueError as e:
            raise ValueError(f"language must be 'pt', got {language!r}") from e
        examples = repo.list_style_examples(lang)
        if not examples:
            return f"No style examples for {language}."
        return "\n\n---\n\n".join(e.text for e in examples)

    return [read_sponsors, read_style_examples]
