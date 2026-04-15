"""Load sponsors and style examples from on-disk files into the DB.

Sponsors live in YAML (a list of objects with name/handles/hashtag).
Style examples live in markdown, with `---` separating individual examples.
Both loaders REPLACE the existing rows on each call (full-refresh semantics).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from cycling_agent.db.models import Language, Sponsor, StyleExample
from cycling_agent.db.repo import Repository


def load_sponsors(path: Path, repo: Repository) -> None:
    """Load sponsor list from YAML, replacing all rows."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ValueError(f"invalid yaml in {path}: {e}") from e

    if not isinstance(raw, list):
        raise ValueError(f"sponsors yaml must be a list of objects, got {type(raw).__name__}")

    sponsors = []
    for entry in raw:
        if not isinstance(entry, dict) or "name" not in entry:
            raise ValueError(f"each sponsor entry must be a dict with 'name', got {entry!r}")
        sponsors.append(
            Sponsor(
                name=entry["name"],
                handle_facebook=entry.get("handle_facebook"),
                handle_instagram=entry.get("handle_instagram"),
                hashtag=entry.get("hashtag"),
            )
        )
    repo.replace_sponsors(sponsors)


def load_style_examples(path: Path, language: Language, repo: Repository) -> None:
    """Load style examples from a markdown file, split on `---` lines.

    Each non-empty paragraph between separators becomes one StyleExample.
    """
    text = path.read_text(encoding="utf-8")
    blocks = [b.strip() for b in text.split("\n---\n")]
    examples = [StyleExample(language=language, text=b) for b in blocks if b]
    repo.replace_style_examples(examples)
