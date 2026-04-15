"""Tests for sponsor and style-example file loaders."""

from __future__ import annotations

from pathlib import Path

import pytest

from cycling_agent.db.engine import build_engine, build_session_factory, init_schema
from cycling_agent.db.loaders import load_sponsors, load_style_examples
from cycling_agent.db.models import Language
from cycling_agent.db.repo import Repository


@pytest.fixture()
def repo() -> Repository:
    engine = build_engine(":memory:")
    init_schema(engine)
    return Repository(build_session_factory(engine))


def test_load_sponsors_writes_to_db(tmp_path: Path, repo: Repository) -> None:
    yaml_path = tmp_path / "sponsors.yaml"
    yaml_path.write_text(
        """
- name: BrandX
  handle_facebook: "@brandx"
  handle_instagram: "@brandx_ig"
  hashtag: "#brandx"
- name: BrandY
  handle_facebook: "@brandy"
  handle_instagram: "@brandy"
  hashtag: "#brandy"
"""
    )
    load_sponsors(yaml_path, repo)
    sponsors = repo.list_sponsors()
    assert {s.name for s in sponsors} == {"BrandX", "BrandY"}


def test_load_sponsors_replaces_previous(tmp_path: Path, repo: Repository) -> None:
    p = tmp_path / "sponsors.yaml"
    p.write_text("- name: A\n")
    load_sponsors(p, repo)
    p.write_text("- name: B\n")
    load_sponsors(p, repo)
    assert {s.name for s in repo.list_sponsors()} == {"B"}


def test_load_style_examples_splits_paragraphs(tmp_path: Path, repo: Repository) -> None:
    md = tmp_path / "style_pt.md"
    md.write_text(
        "Primeiro post sobre uma vitória.\n\n"
        "---\n\n"
        "Segundo post, dia duro mas grato.\n"
    )
    load_style_examples(md, Language.PT, repo)
    examples = repo.list_style_examples(Language.PT)
    assert len(examples) == 2


def test_load_sponsors_invalid_yaml_raises(tmp_path: Path, repo: Repository) -> None:
    p = tmp_path / "sponsors.yaml"
    p.write_text("not: valid: yaml: ::: ::")
    with pytest.raises(ValueError):
        load_sponsors(p, repo)
