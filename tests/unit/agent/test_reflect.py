"""Tests for the reflect command."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cycling_agent.agent.reflect import run_reflect
from cycling_agent.db.engine import build_engine, build_session_factory, init_schema
from cycling_agent.db.models import Language, Platform, StyleExample
from cycling_agent.db.repo import Repository


@pytest.fixture()
def repo() -> Repository:
    engine = build_engine(":memory:")
    init_schema(engine)
    repo = Repository(build_session_factory(engine))
    repo.upsert_activity(id=1, started_at=dt.datetime(2026, 4, 1), name="Race", workout_type=11)
    did = repo.create_draft(activity_id=1, platform=Platform.FACEBOOK, language=Language.PT, caption="x")
    repo.log_approval_event(draft_id=did, event="edited", payload='{"new_caption":"y"}')
    repo.replace_style_examples([StyleExample(language=Language.PT, text="example")])
    return repo


def test_run_reflect_writes_proposal_file(repo: Repository, tmp_path: Path) -> None:
    fake_llm = MagicMock()
    fake_llm.invoke.return_value.content = "## ADD\n\n- example\n"
    out_dir = tmp_path / "reflect-proposals"
    path = run_reflect(
        repo=repo,
        llm=fake_llm,
        output_dir=out_dir,
        now=dt.datetime(2026, 4, 15, 12, 0),
        lookback_days=30,
    )
    assert path.exists()
    assert "ADD" in path.read_text()
    fake_llm.invoke.assert_called_once()


def test_run_reflect_with_no_events_writes_empty_proposal(tmp_path: Path) -> None:
    engine = build_engine(":memory:")
    init_schema(engine)
    repo = Repository(build_session_factory(engine))

    fake_llm = MagicMock()
    fake_llm.invoke.return_value.content = "(no events to reflect on)"
    out_dir = tmp_path / "reflect-proposals"
    path = run_reflect(
        repo=repo, llm=fake_llm, output_dir=out_dir,
        now=dt.datetime(2026, 4, 15, 12, 0), lookback_days=30,
    )
    assert path.exists()
