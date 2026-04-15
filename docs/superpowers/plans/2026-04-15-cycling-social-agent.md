# Cycling Social Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a personal automation agent that detects race activities on Strava, generates approval-gated social posts for Facebook + Instagram in PT and EN, and publishes them at a scheduled time after Telegram approval.

**Architecture:** A DeepAgents orchestrator runs on a scheduler tick. It uses tools (Strava, media, content, approval, publish, state) and spawns a drafter sub-agent per (platform × language) draft. Approval is mediated through SQLite — the Telegram bot writes user actions to the DB, the agent reads on the next cycle. Tools enforce ordering invariants (e.g., publish refuses unless approved; approve refuses if sponsors missing). State is durable across laptop sleep.

**Tech Stack:** Python 3.12+, uv, SQLAlchemy 2.x (sync) + SQLite, langchain, langgraph, deepagents, python-telegram-bot v21+, stravalib v2, facebook-business SDK, Pillow, staticmaps (for route map), pydantic-settings, structlog, ruff, ty, pytest (asyncio_mode=auto), respx (HTTP mocks).

**Spec:** `docs/superpowers/specs/2026-04-15-cycling-social-agent-design.md`

---

## Phasing

The plan is organized into 6 phases that build bottom-up. Each phase produces working, testable software:

1. **Foundations** (T1–T3) — repo scaffold, config, logging.
2. **Database** (T4–T7) — models, repository, init/seed CLI.
3. **External adapters** (T8–T15) — Strava client, media renderers, FB/IG publishers, Telegram bot.
4. **Agent tools** (T16–T19) — the deep-agent tool modules with invariants.
5. **Sub-agents and orchestrator** (T20–T23) — drafter, reflector, orchestrator, runner.
6. **Entry, CLI, smoke test, docs** (T24–T27).

Frequent commits are required — every task ends with a commit. Use Conventional Commits (`feat:`, `fix:`, `chore:`, `test:`, `docs:`).

---

## Conventions used in this plan

- All commands run from the repo root: `~/work/personal/cycling-social-agent/`.
- All dependency adds use `uv add <pkg>==<version>`. **Never edit `pyproject.toml` manually.**
- All Python tests use `uv run pytest`.
- Linting: `uv run ruff check --fix` and `uv run ruff format`.
- Type checking: `uv run ty check src tests`.
- Async tests do not need `@pytest.mark.asyncio` because `asyncio_mode = "auto"` is configured.

---

## Phase 1 — Foundations

### Task 1: Scaffold the project

**Files:**
- Create: `pyproject.toml` (via `uv init`)
- Create: `.gitignore`
- Create: `.env.example`
- Create: `src/cycling_agent/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `README.md` (placeholder)

- [ ] **Step 1: Initialize uv project**

```bash
cd ~/work/personal/cycling-social-agent
uv init --package --name cycling-agent --python 3.12
```

This creates `pyproject.toml`, `src/cycling_agent/__init__.py`, and a `.python-version` file.

- [ ] **Step 2: Add runtime dependencies**

```bash
uv add \
  "langchain==0.3.27" \
  "langgraph==0.2.74" \
  "deepagents==0.1.0" \
  "langchain-anthropic==0.3.6" \
  "anthropic==0.43.1" \
  "python-telegram-bot[job-queue]==21.10" \
  "stravalib==2.2" \
  "facebook-business==21.0.5" \
  "pillow==11.1.0" \
  "py-staticmaps==0.4.0" \
  "sqlalchemy==2.0.36" \
  "pydantic==2.10.5" \
  "pydantic-settings==2.7.1" \
  "structlog==24.4.0" \
  "rich==13.9.4" \
  "click==8.1.8" \
  "pyyaml==6.0.2" \
  "dateparser==1.2.0" \
  "tzdata==2024.2"
```

If any of these versions resolve incorrectly, pin to the latest compatible release as reported by `uv add` and update this step.

- [ ] **Step 3: Add dev dependencies**

```bash
uv add --dev \
  "pytest==8.3.4" \
  "pytest-asyncio==0.25.2" \
  "pytest-cov==6.0.0" \
  "respx==0.22.0" \
  "freezegun==1.5.1" \
  "ruff==0.9.2" \
  "ty==0.0.1a1" \
  "pre-commit==4.0.1"
```

- [ ] **Step 4: Configure pyproject extras (ruff, pytest, ty)**

Append to `pyproject.toml` (after the existing `[project]` section):

```toml
[tool.ruff]
line-length = 120
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP", "SIM", "RUF", "ASYNC"]
ignore = ["E501"]  # line length is enforced by formatter

[tool.ruff.format]
quote-style = "double"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-ra --strict-markers --cov=cycling_agent --cov-report=term-missing"

[tool.ty]
src.root = "src"
```

- [ ] **Step 5: Create `.gitignore`**

```gitignore
# python
__pycache__/
*.py[cod]
*$py.class
.venv/
.python-version
*.egg-info/
build/
dist/

# uv
uv.lock

# env
.env
.env.local

# data
data/cycling.db
data/cycling.db-journal
data/reflect-proposals/
data/media/

# editors
.vscode/
.idea/
*.swp

# pytest / coverage
.pytest_cache/
.coverage
htmlcov/
.ruff_cache/
.ty_cache/
```

Note: We **do** want `uv.lock` committed for reproducible installs in a real project; since this is a single-developer personal app and the user may iterate dependency choices, it is excluded for v1. Revisit before moving to Pi.

- [ ] **Step 6: Create `.env.example`**

```bash
# Strava
STRAVA_CLIENT_ID=
STRAVA_CLIENT_SECRET=
STRAVA_REFRESH_TOKEN=
STRAVA_ATHLETE_ID=

# Meta
META_APP_ID=
META_APP_SECRET=
META_PAGE_ACCESS_TOKEN=
META_PAGE_ID=
META_IG_BUSINESS_ID=

# Telegram
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Anthropic
ANTHROPIC_API_KEY=

# Runtime
POLL_INTERVAL_SECONDS=600
ORCHESTRATOR_MODEL=claude-haiku-4-5-20251001
DRAFTER_MODEL=claude-sonnet-4-6
REFLECTOR_MODEL=claude-sonnet-4-6
DB_PATH=./data/cycling.db
DRY_RUN=false
LOG_LEVEL=INFO

# Scheduling
PUBLISH_TIME_LOCAL=19:00
PUBLISH_TIMEZONE=Europe/Lisbon
```

- [ ] **Step 7: Create `tests/conftest.py` with a baseline asyncio guard**

```python
"""Pytest fixtures shared across all tests."""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip real secrets so tests never accidentally hit live services."""
    for key in (
        "STRAVA_CLIENT_ID",
        "STRAVA_CLIENT_SECRET",
        "STRAVA_REFRESH_TOKEN",
        "META_APP_ID",
        "META_APP_SECRET",
        "META_PAGE_ACCESS_TOKEN",
        "TELEGRAM_BOT_TOKEN",
        "ANTHROPIC_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv(key, "test-" + key.lower())
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("DB_PATH", ":memory:")
```

- [ ] **Step 8: Create placeholder README.md**

```markdown
# cycling-social-agent

Personal automation agent that turns Strava race activities into approval-gated social posts.

See `docs/superpowers/specs/2026-04-15-cycling-social-agent-design.md` for the design and `docs/superpowers/plans/2026-04-15-cycling-social-agent.md` for the implementation plan.

Setup instructions land here once T27 lands.
```

- [ ] **Step 9: Verify lint + tests run cleanly**

Run:
```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run pytest -q
```

Expected: ruff passes (no files yet beyond placeholders), pytest reports `no tests ran`.

- [ ] **Step 10: Commit**

```bash
git add .
git commit -m "chore: scaffold project with uv, ruff, pytest, ty"
```

---

### Task 2: Configuration module

**Files:**
- Create: `src/cycling_agent/config.py`
- Create: `tests/unit/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_config.py
"""Tests for the typed config loader."""

from __future__ import annotations

import pytest

from cycling_agent.config import Settings


def test_settings_load_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLL_INTERVAL_SECONDS", "300")
    monkeypatch.setenv("PUBLISH_TIME_LOCAL", "20:30")
    monkeypatch.setenv("PUBLISH_TIMEZONE", "Europe/Lisbon")
    monkeypatch.setenv("DRY_RUN", "true")

    settings = Settings()

    assert settings.poll_interval_seconds == 300
    assert settings.publish_time_local == "20:30"
    assert settings.publish_timezone == "Europe/Lisbon"
    assert settings.dry_run is True


def test_settings_publish_time_validates_format(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PUBLISH_TIME_LOCAL", "not-a-time")
    with pytest.raises(ValueError, match="HH:MM"):
        Settings()


def test_settings_default_models() -> None:
    settings = Settings()
    assert "haiku" in settings.orchestrator_model.lower()
    assert "sonnet" in settings.drafter_model.lower()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_config.py -v
```

Expected: import error — `cycling_agent.config` does not exist.

- [ ] **Step 3: Implement the config module**

```python
# src/cycling_agent/config.py
"""Typed application settings sourced from environment variables and `.env`."""

from __future__ import annotations

import re

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_HHMM = re.compile(r"^\d{2}:\d{2}$")


class Settings(BaseSettings):
    """All runtime configuration. Read from `.env` then process env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # External services
    strava_client_id: str = ""
    strava_client_secret: str = ""
    strava_refresh_token: str = ""
    strava_athlete_id: str = ""

    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_page_access_token: str = ""
    meta_page_id: str = ""
    meta_ig_business_id: str = ""

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    anthropic_api_key: str = ""

    # Runtime
    poll_interval_seconds: int = Field(default=600, ge=60)
    orchestrator_model: str = "claude-haiku-4-5-20251001"
    drafter_model: str = "claude-sonnet-4-6"
    reflector_model: str = "claude-sonnet-4-6"
    db_path: str = "./data/cycling.db"
    dry_run: bool = False
    log_level: str = "INFO"

    # Scheduling
    publish_time_local: str = "19:00"
    publish_timezone: str = "Europe/Lisbon"

    @field_validator("publish_time_local")
    @classmethod
    def _validate_publish_time(cls, v: str) -> str:
        if not _HHMM.match(v):
            raise ValueError("PUBLISH_TIME_LOCAL must be HH:MM")
        hh, mm = v.split(":")
        if not (0 <= int(hh) < 24 and 0 <= int(mm) < 60):
            raise ValueError("PUBLISH_TIME_LOCAL must be HH:MM with valid hour/minute")
        return v


def load_settings() -> Settings:
    """Module-level loader so tests can override via monkeypatching env."""
    return Settings()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_config.py -v
```

Expected: all three tests pass.

- [ ] **Step 5: Run lint and type-check**

```bash
uv run ruff check src tests
uv run ty check src tests
```

Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add src/cycling_agent/config.py tests/unit/test_config.py
git commit -m "feat(config): add typed Settings via pydantic-settings"
```

---

### Task 3: Logging setup

**Files:**
- Create: `src/cycling_agent/logging.py`
- Create: `tests/unit/test_logging.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_logging.py
"""Tests for structlog configuration."""

from __future__ import annotations

import logging

import structlog

from cycling_agent.logging import configure_logging


def test_configure_logging_sets_level() -> None:
    configure_logging("DEBUG")
    logger = structlog.get_logger("test")
    assert logging.getLogger().level == logging.DEBUG
    # smoke: logger emits without raising
    logger.info("hello", n=1)


def test_configure_logging_invalid_level_raises() -> None:
    import pytest

    with pytest.raises(ValueError, match="invalid log level"):
        configure_logging("NOPE")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_logging.py -v
```

Expected: `ImportError: cannot import name 'configure_logging'`.

- [ ] **Step 3: Implement logging module**

```python
# src/cycling_agent/logging.py
"""Application-wide logging configuration using structlog over stdlib logging."""

from __future__ import annotations

import logging
import sys

import structlog
from rich.console import Console
from rich.logging import RichHandler

_VALID_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def configure_logging(level: str) -> None:
    """Configure stdlib + structlog with rich console output.

    Idempotent: safe to call more than once (e.g., reconfiguring in tests).
    """
    if level not in _VALID_LEVELS:
        raise ValueError(f"invalid log level: {level}")

    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=Console(file=sys.stderr), rich_tracebacks=True)],
        force=True,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level)),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Convenience accessor matching the stdlib pattern."""
    return structlog.get_logger(name)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_logging.py -v
```

Expected: both tests pass.

- [ ] **Step 5: Lint + type check**

```bash
uv run ruff check src tests
uv run ty check src tests
```

- [ ] **Step 6: Commit**

```bash
git add src/cycling_agent/logging.py tests/unit/test_logging.py
git commit -m "feat(logging): add structlog config with rich console handler"
```

---

## Phase 2 — Database

### Task 4: DB engine, base, and all SQLAlchemy models

**Files:**
- Create: `src/cycling_agent/db/__init__.py`
- Create: `src/cycling_agent/db/engine.py`
- Create: `src/cycling_agent/db/models.py`
- Create: `tests/unit/db/__init__.py`
- Create: `tests/unit/db/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/db/test_models.py
"""Tests for the SQLAlchemy model layer."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from cycling_agent.db.engine import build_engine, build_session_factory, init_schema
from cycling_agent.db.models import (
    Activity,
    ActivityStatus,
    ApprovalEvent,
    Draft,
    DraftStatus,
    Language,
    Platform,
    Post,
    Sponsor,
    StyleExample,
)


def _session():
    engine = build_engine(":memory:")
    init_schema(engine)
    return build_session_factory(engine)()


def test_activity_default_status_is_detected() -> None:
    s = _session()
    a = Activity(id=1, started_at=dt.datetime(2026, 4, 1, 10, 0), name="Crit", workout_type=11)
    s.add(a)
    s.commit()
    assert a.status == ActivityStatus.DETECTED


def test_draft_unique_per_activity_platform_language() -> None:
    import pytest
    from sqlalchemy.exc import IntegrityError

    s = _session()
    s.add(Activity(id=1, started_at=dt.datetime(2026, 4, 1), name="r", workout_type=11))
    s.add(Draft(activity_id=1, platform=Platform.FACEBOOK, language=Language.PT, caption="x"))
    s.commit()
    s.add(Draft(activity_id=1, platform=Platform.FACEBOOK, language=Language.PT, caption="y"))
    with pytest.raises(IntegrityError):
        s.commit()


def test_draft_default_state_is_pending() -> None:
    s = _session()
    s.add(Activity(id=1, started_at=dt.datetime(2026, 4, 1), name="r", workout_type=11))
    d = Draft(activity_id=1, platform=Platform.INSTAGRAM, language=Language.EN, caption="x")
    s.add(d)
    s.commit()
    assert d.status == DraftStatus.PENDING
    assert d.post_now is False
    assert d.regenerate_count == 0


def test_post_links_to_draft() -> None:
    s = _session()
    s.add(Activity(id=1, started_at=dt.datetime(2026, 4, 1), name="r", workout_type=11))
    d = Draft(activity_id=1, platform=Platform.FACEBOOK, language=Language.PT, caption="x")
    s.add(d)
    s.commit()
    s.add(Post(draft_id=d.id, platform=Platform.FACEBOOK, external_post_id="123_456"))
    s.commit()
    fetched = s.execute(select(Post).where(Post.draft_id == d.id)).scalar_one()
    assert fetched.external_post_id == "123_456"


def test_sponsor_basic_create() -> None:
    s = _session()
    sponsor = Sponsor(name="BrandX", handle_facebook="@brandx", handle_instagram="@brandx", hashtag="#brandx")
    s.add(sponsor)
    s.commit()
    assert sponsor.id is not None


def test_style_example_per_language() -> None:
    s = _session()
    s.add(StyleExample(language=Language.PT, text="Dia duro mas feliz."))
    s.add(StyleExample(language=Language.EN, text="Hard day, happy ending."))
    s.commit()
    assert s.query(StyleExample).count() == 2


def test_approval_event_audit_trail() -> None:
    s = _session()
    s.add(Activity(id=1, started_at=dt.datetime(2026, 4, 1), name="r", workout_type=11))
    d = Draft(activity_id=1, platform=Platform.FACEBOOK, language=Language.PT, caption="x")
    s.add(d)
    s.commit()
    s.add(ApprovalEvent(draft_id=d.id, event="approved", payload="{}"))
    s.commit()
    assert s.query(ApprovalEvent).count() == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/db/test_models.py -v
```

Expected: ImportError on `cycling_agent.db.engine`.

- [ ] **Step 3: Implement engine module**

```python
# src/cycling_agent/db/__init__.py
"""SQLAlchemy database layer."""
```

```python
# src/cycling_agent/db/engine.py
"""Engine and session factory builders.

Synchronous SQLAlchemy 2.x is used throughout the app. Async tools wrap
repository calls in ``asyncio.to_thread`` to keep DB code simple and
sync-friendly while remaining compatible with the async agent loop.
"""

from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from cycling_agent.db.models import Base


def build_engine(db_path: str) -> Engine:
    """Build a sync SQLAlchemy engine for SQLite. ``:memory:`` is supported."""
    url = "sqlite:///:memory:" if db_path == ":memory:" else f"sqlite:///{db_path}"
    return create_engine(url, future=True, echo=False)


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def init_schema(engine: Engine) -> None:
    """Create all tables. Safe to call repeatedly (no-op if tables exist)."""
    Base.metadata.create_all(engine)
```

- [ ] **Step 4: Implement models module**

```python
# src/cycling_agent/db/models.py
"""ORM models for the cycling agent.

State machines:
- Activity: detected -> drafting -> awaiting_approval -> processed
- Draft: pending -> drafted -> awaiting_approval -> approved -> scheduled -> published
                                                          -> rejected | editing | regenerating
"""

from __future__ import annotations

import datetime as dt
import enum
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Common base for all models."""


class Platform(str, enum.Enum):
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"


class Language(str, enum.Enum):
    PT = "pt"
    EN = "en"


class ActivityStatus(str, enum.Enum):
    DETECTED = "detected"
    DRAFTING = "drafting"
    AWAITING_APPROVAL = "awaiting_approval"
    PROCESSED = "processed"


class DraftStatus(str, enum.Enum):
    PENDING = "pending"
    DRAFTED = "drafted"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    REJECTED = "rejected"
    EDITING = "editing"
    REGENERATING = "regenerating"


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # Strava activity id
    started_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    workout_type: Mapped[int] = mapped_column(Integer, nullable=False)
    feeling_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[ActivityStatus] = mapped_column(
        String(32), default=ActivityStatus.DETECTED, nullable=False
    )
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now, nullable=False)
    processed_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime, nullable=True)

    drafts: Mapped[list["Draft"]] = relationship(back_populates="activity", cascade="all, delete-orphan")


class Draft(Base):
    __tablename__ = "drafts"
    __table_args__ = (
        UniqueConstraint("activity_id", "platform", "language", name="uq_draft_per_combo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id"), nullable=False)
    platform: Mapped[Platform] = mapped_column(String(16), nullable=False)
    language: Mapped[Language] = mapped_column(String(8), nullable=False)
    caption: Mapped[str] = mapped_column(Text, nullable=False)
    hashtags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    media_paths: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # comma-separated
    status: Mapped[DraftStatus] = mapped_column(
        String(32), default=DraftStatus.PENDING, nullable=False
    )
    telegram_message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    feedback_hint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    regenerate_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    scheduled_for: Mapped[Optional[dt.datetime]] = mapped_column(DateTime, nullable=True)
    post_now: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now, onupdate=_now, nullable=False)

    activity: Mapped[Activity] = relationship(back_populates="drafts")


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("drafts.id"), nullable=False)
    platform: Mapped[Platform] = mapped_column(String(16), nullable=False)
    external_post_id: Mapped[str] = mapped_column(String(255), nullable=False)
    published_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now, nullable=False)


class Sponsor(Base):
    __tablename__ = "sponsors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    handle_facebook: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    handle_instagram: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    hashtag: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class StyleExample(Base):
    __tablename__ = "style_examples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    language: Mapped[Language] = mapped_column(String(8), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now, nullable=False)
    finished_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime, nullable=True)
    tool_call_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_estimate_usd: Mapped[float] = mapped_column(default=0.0, nullable=False)
    outcome: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    error_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class ApprovalEvent(Base):
    __tablename__ = "approval_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("drafts.id"), nullable=False)
    event: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now, nullable=False)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/unit/db/test_models.py -v
```

Expected: all 7 tests pass.

- [ ] **Step 6: Lint + type check**

```bash
uv run ruff check src tests
uv run ty check src tests
```

- [ ] **Step 7: Commit**

```bash
git add src/cycling_agent/db tests/unit/db
git commit -m "feat(db): add SQLAlchemy engine and ORM models"
```

---

### Task 5: Repository module (CRUD + queries)

**Files:**
- Create: `src/cycling_agent/db/repo.py`
- Create: `tests/unit/db/test_repo.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/db/test_repo.py
"""Tests for the repository façade over the ORM."""

from __future__ import annotations

import datetime as dt

import pytest

from cycling_agent.db.engine import build_engine, build_session_factory, init_schema
from cycling_agent.db.models import ActivityStatus, DraftStatus, Language, Platform
from cycling_agent.db.repo import Repository


@pytest.fixture()
def repo() -> Repository:
    engine = build_engine(":memory:")
    init_schema(engine)
    return Repository(build_session_factory(engine))


def test_upsert_activity_inserts_new(repo: Repository) -> None:
    repo.upsert_activity(id=1, started_at=dt.datetime(2026, 4, 1), name="Crit", workout_type=11)
    activities = repo.list_activities_in_states([ActivityStatus.DETECTED])
    assert len(activities) == 1


def test_upsert_activity_idempotent(repo: Repository) -> None:
    repo.upsert_activity(id=1, started_at=dt.datetime(2026, 4, 1), name="Crit", workout_type=11)
    repo.upsert_activity(id=1, started_at=dt.datetime(2026, 4, 1), name="Crit", workout_type=11)
    assert len(repo.list_activities_in_states([ActivityStatus.DETECTED])) == 1


def test_set_feeling_text(repo: Repository) -> None:
    repo.upsert_activity(id=1, started_at=dt.datetime(2026, 4, 1), name="Crit", workout_type=11)
    repo.set_feeling_text(activity_id=1, text="rainy crit, top 20")
    a = repo.get_activity(1)
    assert a is not None
    assert a.feeling_text == "rainy crit, top 20"


def test_create_draft_returns_id(repo: Repository) -> None:
    repo.upsert_activity(id=1, started_at=dt.datetime(2026, 4, 1), name="Crit", workout_type=11)
    draft_id = repo.create_draft(
        activity_id=1, platform=Platform.FACEBOOK, language=Language.PT,
        caption="hello", hashtags="#x", media_paths="/tmp/a.png",
    )
    assert draft_id > 0
    d = repo.get_draft(draft_id)
    assert d is not None
    assert d.status == DraftStatus.DRAFTED  # repo upgrades from PENDING -> DRAFTED on create


def test_set_draft_status(repo: Repository) -> None:
    repo.upsert_activity(id=1, started_at=dt.datetime(2026, 4, 1), name="Crit", workout_type=11)
    did = repo.create_draft(activity_id=1, platform=Platform.FACEBOOK, language=Language.PT, caption="x")
    repo.set_draft_status(did, DraftStatus.AWAITING_APPROVAL, telegram_message_id=42)
    d = repo.get_draft(did)
    assert d is not None
    assert d.status == DraftStatus.AWAITING_APPROVAL
    assert d.telegram_message_id == 42


def test_find_due_drafts_returns_scheduled_past(repo: Repository) -> None:
    repo.upsert_activity(id=1, started_at=dt.datetime(2026, 4, 1), name="Crit", workout_type=11)
    did = repo.create_draft(activity_id=1, platform=Platform.FACEBOOK, language=Language.PT, caption="x")
    past = dt.datetime.now(dt.UTC) - dt.timedelta(minutes=5)
    repo.schedule_draft(did, past.replace(tzinfo=None))
    due = repo.find_due_drafts(now=dt.datetime.now(dt.UTC))
    assert [d.id for d in due] == [did]


def test_find_due_drafts_includes_post_now_approved(repo: Repository) -> None:
    repo.upsert_activity(id=1, started_at=dt.datetime(2026, 4, 1), name="Crit", workout_type=11)
    did = repo.create_draft(activity_id=1, platform=Platform.FACEBOOK, language=Language.PT, caption="x")
    repo.set_approved(did, post_now=True)
    due = repo.find_due_drafts(now=dt.datetime.now(dt.UTC))
    assert [d.id for d in due] == [did]


def test_record_post_marks_published(repo: Repository) -> None:
    repo.upsert_activity(id=1, started_at=dt.datetime(2026, 4, 1), name="Crit", workout_type=11)
    did = repo.create_draft(activity_id=1, platform=Platform.FACEBOOK, language=Language.PT, caption="x")
    repo.set_approved(did, post_now=True)
    repo.record_post(draft_id=did, platform=Platform.FACEBOOK, external_post_id="abc")
    d = repo.get_draft(did)
    assert d is not None
    assert d.status == DraftStatus.PUBLISHED


def test_mark_processed_requires_all_terminal(repo: Repository) -> None:
    repo.upsert_activity(id=1, started_at=dt.datetime(2026, 4, 1), name="Crit", workout_type=11)
    d1 = repo.create_draft(activity_id=1, platform=Platform.FACEBOOK, language=Language.PT, caption="x")
    repo.create_draft(activity_id=1, platform=Platform.INSTAGRAM, language=Language.PT, caption="y")
    repo.set_approved(d1, post_now=True)
    repo.record_post(draft_id=d1, platform=Platform.FACEBOOK, external_post_id="abc")
    # second draft still in DRAFTED
    with pytest.raises(ValueError, match="not all drafts terminal"):
        repo.mark_processed(activity_id=1)


def test_log_approval_event(repo: Repository) -> None:
    repo.upsert_activity(id=1, started_at=dt.datetime(2026, 4, 1), name="Crit", workout_type=11)
    did = repo.create_draft(activity_id=1, platform=Platform.FACEBOOK, language=Language.PT, caption="x")
    repo.log_approval_event(draft_id=did, event="approved", payload='{"post_now": false}')
    events = repo.list_approval_events_for_draft(did)
    assert len(events) == 1
    assert events[0].event == "approved"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/db/test_repo.py -v
```

Expected: import error.

- [ ] **Step 3: Implement the repository**

```python
# src/cycling_agent/db/repo.py
"""Repository façade over the ORM session.

All write methods commit on success. All read methods are query-only.
Idempotent where the spec requires it (upsert_activity, record_post).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from typing import Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, sessionmaker

from cycling_agent.db.models import (
    Activity,
    ActivityStatus,
    ApprovalEvent,
    Draft,
    DraftStatus,
    Language,
    Platform,
    Post,
    Sponsor,
    StyleExample,
)

_TERMINAL_DRAFT_STATUSES = (DraftStatus.PUBLISHED, DraftStatus.REJECTED)


class Repository:
    """Thin sync repository. Inject a session factory; one session per call."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    # --- activities ----------------------------------------------------------

    def upsert_activity(
        self, *, id: int, started_at: dt.datetime, name: str, workout_type: int
    ) -> None:
        with self._session_factory() as s:
            existing = s.get(Activity, id)
            if existing is None:
                s.add(Activity(id=id, started_at=started_at, name=name, workout_type=workout_type))
            else:
                existing.started_at = started_at
                existing.name = name
                existing.workout_type = workout_type
            s.commit()

    def get_activity(self, activity_id: int) -> Optional[Activity]:
        with self._session_factory() as s:
            return s.get(Activity, activity_id)

    def set_feeling_text(self, *, activity_id: int, text: str) -> None:
        with self._session_factory() as s:
            a = s.get(Activity, activity_id)
            if a is None:
                raise ValueError(f"activity {activity_id} not found")
            a.feeling_text = text
            s.commit()

    def list_activities_in_states(
        self, statuses: Sequence[ActivityStatus]
    ) -> list[Activity]:
        with self._session_factory() as s:
            stmt = select(Activity).where(Activity.status.in_(list(statuses)))
            return list(s.execute(stmt).scalars().all())

    def set_activity_status(self, activity_id: int, status: ActivityStatus) -> None:
        with self._session_factory() as s:
            a = s.get(Activity, activity_id)
            if a is None:
                raise ValueError(f"activity {activity_id} not found")
            a.status = status
            if status == ActivityStatus.PROCESSED:
                a.processed_at = dt.datetime.now(dt.UTC)
            s.commit()

    def mark_processed(self, activity_id: int) -> None:
        with self._session_factory() as s:
            a = s.get(Activity, activity_id)
            if a is None:
                raise ValueError(f"activity {activity_id} not found")
            non_terminal = [d for d in a.drafts if d.status not in _TERMINAL_DRAFT_STATUSES]
            if non_terminal:
                raise ValueError("not all drafts terminal")
            a.status = ActivityStatus.PROCESSED
            a.processed_at = dt.datetime.now(dt.UTC)
            s.commit()

    # --- drafts --------------------------------------------------------------

    def create_draft(
        self,
        *,
        activity_id: int,
        platform: Platform,
        language: Language,
        caption: str,
        hashtags: Optional[str] = None,
        media_paths: Optional[str] = None,
    ) -> int:
        with self._session_factory() as s:
            d = Draft(
                activity_id=activity_id,
                platform=platform,
                language=language,
                caption=caption,
                hashtags=hashtags,
                media_paths=media_paths,
                status=DraftStatus.DRAFTED,
            )
            s.add(d)
            s.commit()
            return d.id

    def get_draft(self, draft_id: int) -> Optional[Draft]:
        with self._session_factory() as s:
            return s.get(Draft, draft_id)

    def get_draft_by_telegram_message(self, message_id: int) -> Optional[Draft]:
        with self._session_factory() as s:
            stmt = select(Draft).where(Draft.telegram_message_id == message_id)
            return s.execute(stmt).scalar_one_or_none()

    def set_draft_status(
        self,
        draft_id: int,
        status: DraftStatus,
        *,
        telegram_message_id: Optional[int] = None,
        feedback_hint: Optional[str] = None,
        caption: Optional[str] = None,
    ) -> None:
        with self._session_factory() as s:
            d = s.get(Draft, draft_id)
            if d is None:
                raise ValueError(f"draft {draft_id} not found")
            d.status = status
            if telegram_message_id is not None:
                d.telegram_message_id = telegram_message_id
            if feedback_hint is not None:
                d.feedback_hint = feedback_hint
            if caption is not None:
                d.caption = caption
            s.commit()

    def increment_regenerate_count(self, draft_id: int) -> int:
        with self._session_factory() as s:
            d = s.get(Draft, draft_id)
            if d is None:
                raise ValueError(f"draft {draft_id} not found")
            d.regenerate_count += 1
            s.commit()
            return d.regenerate_count

    def set_approved(self, draft_id: int, *, post_now: bool) -> None:
        with self._session_factory() as s:
            d = s.get(Draft, draft_id)
            if d is None:
                raise ValueError(f"draft {draft_id} not found")
            d.status = DraftStatus.APPROVED
            d.post_now = post_now
            s.commit()

    def schedule_draft(self, draft_id: int, scheduled_for: dt.datetime) -> None:
        with self._session_factory() as s:
            d = s.get(Draft, draft_id)
            if d is None:
                raise ValueError(f"draft {draft_id} not found")
            if d.status != DraftStatus.APPROVED:
                raise ValueError(f"can only schedule approved drafts, got {d.status}")
            d.scheduled_for = scheduled_for
            d.status = DraftStatus.SCHEDULED
            s.commit()

    def reschedule_draft(self, draft_id: int, scheduled_for: dt.datetime) -> None:
        with self._session_factory() as s:
            d = s.get(Draft, draft_id)
            if d is None:
                raise ValueError(f"draft {draft_id} not found")
            if d.status != DraftStatus.SCHEDULED:
                raise ValueError(f"can only reschedule scheduled drafts, got {d.status}")
            d.scheduled_for = scheduled_for
            s.commit()

    def find_due_drafts(self, *, now: dt.datetime) -> list[Draft]:
        """Drafts ready to publish: scheduled past due, OR approved with post_now."""
        now_naive = now.replace(tzinfo=None) if now.tzinfo else now
        with self._session_factory() as s:
            stmt = select(Draft).where(
                or_(
                    and_(Draft.status == DraftStatus.SCHEDULED, Draft.scheduled_for <= now_naive),
                    and_(Draft.status == DraftStatus.APPROVED, Draft.post_now.is_(True)),
                )
            )
            return list(s.execute(stmt).scalars().all())

    def list_drafts_in_states(
        self, statuses: Sequence[DraftStatus]
    ) -> list[Draft]:
        with self._session_factory() as s:
            stmt = select(Draft).where(Draft.status.in_(list(statuses)))
            return list(s.execute(stmt).scalars().all())

    # --- posts ---------------------------------------------------------------

    def record_post(
        self, *, draft_id: int, platform: Platform, external_post_id: str
    ) -> None:
        with self._session_factory() as s:
            d = s.get(Draft, draft_id)
            if d is None:
                raise ValueError(f"draft {draft_id} not found")
            existing = s.execute(
                select(Post).where(
                    Post.draft_id == draft_id, Post.platform == platform
                )
            ).scalar_one_or_none()
            if existing is not None:
                return  # idempotent
            s.add(Post(draft_id=draft_id, platform=platform, external_post_id=external_post_id))
            d.status = DraftStatus.PUBLISHED
            s.commit()

    # --- sponsors / style examples ------------------------------------------

    def replace_sponsors(self, sponsors: Sequence[Sponsor]) -> None:
        with self._session_factory() as s:
            s.query(Sponsor).delete()
            for sp in sponsors:
                s.add(sp)
            s.commit()

    def list_sponsors(self) -> list[Sponsor]:
        with self._session_factory() as s:
            return list(s.execute(select(Sponsor)).scalars().all())

    def replace_style_examples(self, examples: Sequence[StyleExample]) -> None:
        with self._session_factory() as s:
            s.query(StyleExample).delete()
            for ex in examples:
                s.add(ex)
            s.commit()

    def list_style_examples(self, language: Language) -> list[StyleExample]:
        with self._session_factory() as s:
            stmt = select(StyleExample).where(
                StyleExample.language == language, StyleExample.enabled.is_(True)
            )
            return list(s.execute(stmt).scalars().all())

    # --- approval events -----------------------------------------------------

    def log_approval_event(self, *, draft_id: int, event: str, payload: str) -> None:
        with self._session_factory() as s:
            s.add(ApprovalEvent(draft_id=draft_id, event=event, payload=payload))
            s.commit()

    def list_approval_events_for_draft(self, draft_id: int) -> list[ApprovalEvent]:
        with self._session_factory() as s:
            stmt = (
                select(ApprovalEvent)
                .where(ApprovalEvent.draft_id == draft_id)
                .order_by(ApprovalEvent.at)
            )
            return list(s.execute(stmt).scalars().all())

    def list_recent_approval_events(self, *, since: dt.datetime) -> list[ApprovalEvent]:
        with self._session_factory() as s:
            stmt = (
                select(ApprovalEvent)
                .where(ApprovalEvent.at >= since)
                .order_by(ApprovalEvent.at)
            )
            return list(s.execute(stmt).scalars().all())
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/db/test_repo.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Lint + type check**

```bash
uv run ruff check src tests
uv run ty check src tests
```

- [ ] **Step 6: Commit**

```bash
git add src/cycling_agent/db/repo.py tests/unit/db/test_repo.py
git commit -m "feat(db): add Repository façade with idempotent upsert/record_post"
```

---

### Task 6: Init-db CLI + sponsor / style-example seeders

**Files:**
- Create: `src/cycling_agent/cli.py` (basic skeleton; expanded later)
- Create: `src/cycling_agent/db/loaders.py`
- Create: `data/sponsors.yaml.example`
- Create: `data/style_examples_pt.md.example`
- Create: `data/style_examples_en.md.example`
- Create: `tests/unit/db/test_loaders.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/db/test_loaders.py
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/db/test_loaders.py -v
```

Expected: import error.

- [ ] **Step 3: Implement loaders**

```python
# src/cycling_agent/db/loaders.py
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
```

- [ ] **Step 4: Implement the CLI skeleton with init-db and seed commands**

```python
# src/cycling_agent/cli.py
"""Click-based CLI entrypoint.

Subcommands implemented in this task:
- init-db: create the SQLite schema.
- seed-sponsors: load sponsors.yaml into the DB.
- seed-style: load style example markdown files into the DB.

Additional subcommands (serve, reflect, dry-run helpers) land in later tasks.
"""

from __future__ import annotations

from pathlib import Path

import click

from cycling_agent.config import load_settings
from cycling_agent.db.engine import build_engine, build_session_factory, init_schema
from cycling_agent.db.loaders import load_sponsors, load_style_examples
from cycling_agent.db.models import Language
from cycling_agent.db.repo import Repository
from cycling_agent.logging import configure_logging, get_logger

log = get_logger(__name__)


def _build_repo() -> Repository:
    settings = load_settings()
    configure_logging(settings.log_level)
    engine = build_engine(settings.db_path)
    init_schema(engine)
    return Repository(build_session_factory(engine))


@click.group()
def cli() -> None:
    """cycling-agent CLI."""


@cli.command("init-db")
def init_db_cmd() -> None:
    """Create the SQLite schema (no-op if already created)."""
    _build_repo()
    click.echo("schema initialised")


@cli.command("seed-sponsors")
@click.option("--path", type=click.Path(exists=True, dir_okay=False, path_type=Path),
              default=Path("data/sponsors.yaml"))
def seed_sponsors_cmd(path: Path) -> None:
    """Reload sponsors from YAML."""
    repo = _build_repo()
    load_sponsors(path, repo)
    click.echo(f"loaded {len(repo.list_sponsors())} sponsors from {path}")


@cli.command("seed-style")
@click.option("--lang", type=click.Choice(["pt", "en"]), required=True)
@click.option("--path", type=click.Path(exists=True, dir_okay=False, path_type=Path), required=True)
def seed_style_cmd(lang: str, path: Path) -> None:
    """Reload style examples from a markdown file."""
    repo = _build_repo()
    load_style_examples(path, Language(lang), repo)
    click.echo(f"loaded {len(repo.list_style_examples(Language(lang)))} examples for {lang}")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
```

Add a `[project.scripts]` entry to `pyproject.toml`:

```toml
[project.scripts]
cycling-agent = "cycling_agent.cli:main"
```

- [ ] **Step 5: Add example data files**

```yaml
# data/sponsors.yaml.example
- name: BrandX
  handle_facebook: "@brandx"
  handle_instagram: "@brandx"
  hashtag: "#brandx"

- name: BrandY
  handle_facebook: "@brandy"
  handle_instagram: "@brandy"
  hashtag: "#brandy"
```

```markdown
<!-- data/style_examples_pt.md.example -->
Dia duro hoje. Caí no grupo da frente, sofri nas últimas duas voltas e ainda assim consegui top 15. Obrigado @brandx e @brandy por estarem comigo. #brandx #brandy

---

Vitória inesperada na etapa de hoje. Plano da equipa funcionou perfeitamente. Power normalizado de 305W nas últimas duas horas. Obrigado @brandx e @brandy. #brandx #brandy
```

```markdown
<!-- data/style_examples_en.md.example -->
Tough day at the office. Got dropped on the third lap, fought back, finished top 30. Thanks @brandx and @brandy for the unwavering support. #brandx #brandy

---

Unexpected stage win. Tactics played out exactly as we discussed in the bus. NP 305W for the final two hours. Thank you @brandx and @brandy. #brandx #brandy
```

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/unit/db -v
```

Expected: all tests pass.

- [ ] **Step 7: Smoke-test the CLI end-to-end**

```bash
cp data/sponsors.yaml.example data/sponsors.yaml
cp data/style_examples_pt.md.example data/style_examples_pt.md
cp data/style_examples_en.md.example data/style_examples_en.md
mkdir -p data
DB_PATH=./data/cycling.db uv run cycling-agent init-db
DB_PATH=./data/cycling.db uv run cycling-agent seed-sponsors
DB_PATH=./data/cycling.db uv run cycling-agent seed-style --lang pt --path data/style_examples_pt.md
DB_PATH=./data/cycling.db uv run cycling-agent seed-style --lang en --path data/style_examples_en.md
rm data/cycling.db
```

Expected: each command prints the success message; no errors.

- [ ] **Step 8: Lint + type check**

```bash
uv run ruff check src tests
uv run ty check src tests
```

- [ ] **Step 9: Commit**

```bash
git add src/cycling_agent/cli.py src/cycling_agent/db/loaders.py \
        data/*.example tests/unit/db/test_loaders.py pyproject.toml
git commit -m "feat(cli): add init-db and seed commands"
```

---


## Phase 3 — External adapters

### Task 7: Strava client wrapper

**Files:**
- Create: `src/cycling_agent/strava/__init__.py`
- Create: `src/cycling_agent/strava/client.py`
- Create: `tests/unit/strava/__init__.py`
- Create: `tests/unit/strava/test_client.py`
- Create: `tests/fixtures/strava_race_activity.json`
- Create: `tests/fixtures/strava_training_ride.json`

- [ ] **Step 1: Create test fixtures**

```json
// tests/fixtures/strava_race_activity.json
{
  "id": 14738291734,
  "name": "Volta ao Algarve - Etapa 2",
  "type": "Ride",
  "sport_type": "Ride",
  "workout_type": 11,
  "start_date_local": "2026-02-19T13:30:00Z",
  "distance": 158420.0,
  "moving_time": 12640,
  "elapsed_time": 12780,
  "total_elevation_gain": 1834.0,
  "average_speed": 12.5,
  "average_watts": 268.0,
  "weighted_average_watts": 305.0,
  "average_heartrate": 162.0,
  "max_heartrate": 188.0,
  "kilojoules": 3387.5,
  "description": "Etapa difícil, ataquei a 30km do final, fechei top 15. Pernas vazias mas feliz.",
  "map": {
    "id": "a14738291734",
    "summary_polyline": "}~p_F~ngzAhIb@~CdC|EfDhEzC~D|D~CrEvBfFlBlGfBzG`B|G|A`Hl@vGS~G_AhGoBjFsCpEqDdEqEfDeF~CoFhCqGdCsHvBuI~AwJxAwK~@yLpAyM~AyN`CyOlD",
    "polyline": null
  }
}
```

```json
// tests/fixtures/strava_training_ride.json
{
  "id": 14738200000,
  "name": "Endurance ride",
  "type": "Ride",
  "sport_type": "Ride",
  "workout_type": 10,
  "start_date_local": "2026-02-18T08:00:00Z",
  "distance": 80000.0,
  "moving_time": 9000,
  "elapsed_time": 9100,
  "total_elevation_gain": 600.0,
  "average_speed": 8.9,
  "average_watts": 195.0,
  "weighted_average_watts": 200.0,
  "average_heartrate": 138.0,
  "max_heartrate": 155.0,
  "kilojoules": 1755.0,
  "description": "",
  "map": {"id": "a14738200000", "summary_polyline": "abc", "polyline": null}
}
```

- [ ] **Step 2: Write the failing test**

```python
# tests/unit/strava/test_client.py
"""Tests for the Strava client wrapper."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cycling_agent.strava.client import RaceCodes, StravaActivity, StravaClient

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures"


@pytest.fixture()
def race_payload() -> dict:
    return json.loads((FIXTURE_DIR / "strava_race_activity.json").read_text())


@pytest.fixture()
def training_payload() -> dict:
    return json.loads((FIXTURE_DIR / "strava_training_ride.json").read_text())


def test_is_race_returns_true_for_ride_workout_type_11(race_payload: dict) -> None:
    assert StravaClient.is_race(race_payload) is True


def test_is_race_returns_false_for_endurance_ride(training_payload: dict) -> None:
    assert StravaClient.is_race(training_payload) is False


def test_is_race_handles_run_workout_type_1() -> None:
    assert StravaClient.is_race({"sport_type": "Run", "workout_type": 1}) is True


def test_to_activity_extracts_feeling_from_description(race_payload: dict) -> None:
    a = StravaClient.to_activity(race_payload)
    assert isinstance(a, StravaActivity)
    assert a.id == 14738291734
    assert "ataquei" in (a.feeling_text or "")
    assert a.workout_type == RaceCodes.RIDE


def test_to_activity_normalises_started_at(race_payload: dict) -> None:
    a = StravaClient.to_activity(race_payload)
    assert a.started_at == dt.datetime(2026, 2, 19, 13, 30, 0, tzinfo=dt.UTC)


def test_to_activity_handles_missing_description(training_payload: dict) -> None:
    a = StravaClient.to_activity(training_payload)
    assert a.feeling_text is None or a.feeling_text == ""


def test_list_recent_activities_filters_to_races(race_payload: dict, training_payload: dict) -> None:
    fake_strava = MagicMock()
    fake_strava.get_activities.return_value = [
        _attr_dict(race_payload),
        _attr_dict(training_payload),
    ]
    client = StravaClient(client=fake_strava)
    races = client.list_recent_races(after=dt.datetime(2026, 1, 1, tzinfo=dt.UTC))
    assert [r.id for r in races] == [14738291734]


def _attr_dict(d: dict):
    """Stravalib returns objects with attributes; emulate with a SimpleNamespace."""
    from types import SimpleNamespace
    obj = SimpleNamespace(**d)
    if "map" in d and isinstance(d["map"], dict):
        obj.map = SimpleNamespace(**d["map"])
    return obj


def test_get_activity_detail_calls_stravalib(race_payload: dict) -> None:
    fake_strava = MagicMock()
    fake_strava.get_activity.return_value = _attr_dict(race_payload)
    client = StravaClient(client=fake_strava)
    a = client.get_activity_detail(14738291734)
    fake_strava.get_activity.assert_called_once_with(14738291734, include_all_efforts=True)
    assert a.id == 14738291734
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/unit/strava/test_client.py -v
```

Expected: import error.

- [ ] **Step 4: Implement the Strava client**

```python
# src/cycling_agent/strava/__init__.py
"""Strava integration."""
```

```python
# src/cycling_agent/strava/client.py
"""Strava API wrapper.

Wraps stravalib so the rest of the codebase only sees our typed
``StravaActivity`` dataclass. OAuth token refresh is delegated to
stravalib via ``refresh_access_token``; we cache the access token in
memory for the process lifetime.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import enum
import time
from typing import Any, Optional

import structlog
from stravalib import Client as StravalibClient

log = structlog.get_logger(__name__)


class RaceCodes(int, enum.Enum):
    """Strava workout_type integer codes that mean 'race'."""
    RIDE = 11
    RUN = 1


@dataclasses.dataclass(frozen=True)
class StravaActivity:
    id: int
    name: str
    workout_type: int
    started_at: dt.datetime
    distance_m: float
    moving_time_s: int
    elevation_gain_m: float
    avg_speed_mps: float
    avg_power_w: Optional[float]
    norm_power_w: Optional[float]
    avg_hr: Optional[float]
    max_hr: Optional[float]
    kilojoules: Optional[float]
    feeling_text: Optional[str]
    polyline: Optional[str]


class StravaClient:
    """High-level Strava client used by the rest of the app."""

    def __init__(
        self,
        *,
        client: Optional[StravalibClient] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        refresh_token: Optional[str] = None,
    ) -> None:
        self._client = client or StravalibClient()
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._access_token_expires_at: float = 0.0

    def _ensure_token(self) -> None:
        if self._client_id is None:
            return  # tests inject a pre-built client
        if time.time() < self._access_token_expires_at - 60:
            return
        token_data = self._client.refresh_access_token(
            client_id=int(self._client_id),
            client_secret=self._client_secret,
            refresh_token=self._refresh_token,
        )
        self._client.access_token = token_data["access_token"]
        self._refresh_token = token_data["refresh_token"]
        self._access_token_expires_at = float(token_data["expires_at"])
        log.info("strava.token_refreshed", expires_at=self._access_token_expires_at)

    # --- classmethods used directly by tools ---------------------------------

    @classmethod
    def is_race(cls, payload: Any) -> bool:
        """True iff workout_type matches one of the race codes for the sport."""
        sport = _attr(payload, "sport_type", _attr(payload, "type", None))
        wt = _attr(payload, "workout_type", None)
        if wt is None:
            return False
        if sport == "Run":
            return wt == RaceCodes.RUN.value
        # Default to Ride
        return wt == RaceCodes.RIDE.value

    @classmethod
    def to_activity(cls, payload: Any) -> StravaActivity:
        """Convert raw Strava payload (dict or attr-object) into our typed activity."""
        started = _attr(payload, "start_date_local")
        if isinstance(started, str):
            # ISO-8601, may end in Z
            started_dt = dt.datetime.fromisoformat(started.replace("Z", "+00:00"))
        else:
            started_dt = started
        if started_dt.tzinfo is None:
            started_dt = started_dt.replace(tzinfo=dt.UTC)

        map_obj = _attr(payload, "map", None)
        polyline = _attr(map_obj, "summary_polyline", None) if map_obj is not None else None

        return StravaActivity(
            id=int(_attr(payload, "id")),
            name=str(_attr(payload, "name", "")),
            workout_type=int(_attr(payload, "workout_type", 0) or 0),
            started_at=started_dt,
            distance_m=float(_attr(payload, "distance", 0.0) or 0.0),
            moving_time_s=int(_attr(payload, "moving_time", 0) or 0),
            elevation_gain_m=float(_attr(payload, "total_elevation_gain", 0.0) or 0.0),
            avg_speed_mps=float(_attr(payload, "average_speed", 0.0) or 0.0),
            avg_power_w=_optional_float(_attr(payload, "average_watts", None)),
            norm_power_w=_optional_float(_attr(payload, "weighted_average_watts", None)),
            avg_hr=_optional_float(_attr(payload, "average_heartrate", None)),
            max_hr=_optional_float(_attr(payload, "max_heartrate", None)),
            kilojoules=_optional_float(_attr(payload, "kilojoules", None)),
            feeling_text=_optional_str(_attr(payload, "description", None)),
            polyline=polyline,
        )

    # --- instance methods ----------------------------------------------------

    def list_recent_races(self, *, after: dt.datetime) -> list[StravaActivity]:
        """List race activities started after the given UTC timestamp."""
        self._ensure_token()
        results: list[StravaActivity] = []
        for raw in self._client.get_activities(after=after):
            if self.is_race(raw):
                results.append(self.to_activity(raw))
        return results

    def get_activity_detail(self, activity_id: int) -> StravaActivity:
        """Fetch full activity detail (including description) by id."""
        self._ensure_token()
        raw = self._client.get_activity(activity_id, include_all_efforts=True)
        return self.to_activity(raw)


def _attr(obj: Any, key: str, default: Any = None) -> Any:
    """Resolve attribute or dict-key access with a default."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _optional_float(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    return float(v)


def _optional_str(v: Any) -> Optional[str]:
    if v is None or v == "":
        return None
    return str(v)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/unit/strava -v
```

Expected: all tests pass.

- [ ] **Step 6: Lint + type check**

```bash
uv run ruff check src tests
uv run ty check src tests
```

- [ ] **Step 7: Commit**

```bash
git add src/cycling_agent/strava tests/unit/strava tests/fixtures
git commit -m "feat(strava): wrap stravalib in typed client"
```

---

### Task 8: Strava poller (find new races, dedupe against DB)

**Files:**
- Create: `src/cycling_agent/strava/poller.py`
- Create: `tests/unit/strava/test_poller.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/strava/test_poller.py
"""Tests for the strava poller."""

from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock

import pytest

from cycling_agent.db.engine import build_engine, build_session_factory, init_schema
from cycling_agent.db.repo import Repository
from cycling_agent.strava.client import StravaActivity
from cycling_agent.strava.poller import StravaPoller


@pytest.fixture()
def repo() -> Repository:
    engine = build_engine(":memory:")
    init_schema(engine)
    return Repository(build_session_factory(engine))


def _race(id_: int) -> StravaActivity:
    return StravaActivity(
        id=id_, name=f"Race {id_}", workout_type=11,
        started_at=dt.datetime(2026, 4, 1, 10, 0, tzinfo=dt.UTC),
        distance_m=100000, moving_time_s=10000, elevation_gain_m=1500,
        avg_speed_mps=10.0, avg_power_w=300, norm_power_w=305, avg_hr=160,
        max_hr=185, kilojoules=3000, feeling_text=None, polyline="abc",
    )


def test_poll_inserts_new_races(repo: Repository) -> None:
    fake_strava = MagicMock()
    fake_strava.list_recent_races.return_value = [_race(1), _race(2)]
    poller = StravaPoller(client=fake_strava, repo=repo, lookback_days=7)
    new_ids = poller.poll(now=dt.datetime(2026, 4, 1, 12, 0, tzinfo=dt.UTC))
    assert sorted(new_ids) == [1, 2]


def test_poll_skips_already_known(repo: Repository) -> None:
    fake_strava = MagicMock()
    fake_strava.list_recent_races.return_value = [_race(1)]
    poller = StravaPoller(client=fake_strava, repo=repo, lookback_days=7)
    poller.poll(now=dt.datetime(2026, 4, 1, 12, 0, tzinfo=dt.UTC))
    new_ids = poller.poll(now=dt.datetime(2026, 4, 1, 12, 30, tzinfo=dt.UTC))
    assert new_ids == []


def test_poll_passes_lookback_to_client(repo: Repository) -> None:
    fake_strava = MagicMock()
    fake_strava.list_recent_races.return_value = []
    poller = StravaPoller(client=fake_strava, repo=repo, lookback_days=3)
    now = dt.datetime(2026, 4, 1, 12, 0, tzinfo=dt.UTC)
    poller.poll(now=now)
    fake_strava.list_recent_races.assert_called_once()
    after = fake_strava.list_recent_races.call_args.kwargs["after"]
    assert after == now - dt.timedelta(days=3)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/strava/test_poller.py -v
```

Expected: import error.

- [ ] **Step 3: Implement the poller**

```python
# src/cycling_agent/strava/poller.py
"""Strava poller: fetch recent race activities and persist new ones to the DB."""

from __future__ import annotations

import datetime as dt

import structlog

from cycling_agent.db.repo import Repository
from cycling_agent.strava.client import StravaClient

log = structlog.get_logger(__name__)


class StravaPoller:
    """Glue between :class:`StravaClient` and the :class:`Repository`."""

    def __init__(self, *, client: StravaClient, repo: Repository, lookback_days: int = 7) -> None:
        self._client = client
        self._repo = repo
        self._lookback = dt.timedelta(days=lookback_days)

    def poll(self, *, now: dt.datetime) -> list[int]:
        """Fetch races from `now - lookback_days` and upsert any new ones.

        Returns the list of activity ids that were *newly* inserted.
        """
        races = self._client.list_recent_races(after=now - self._lookback)
        log.info("strava.poll.found", count=len(races))

        new_ids: list[int] = []
        for r in races:
            existing = self._repo.get_activity(r.id)
            self._repo.upsert_activity(
                id=r.id,
                started_at=r.started_at.replace(tzinfo=None),
                name=r.name,
                workout_type=r.workout_type,
            )
            if existing is None:
                new_ids.append(r.id)
                log.info("strava.poll.new_race", id=r.id, name=r.name)

        return new_ids
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/strava -v
```

Expected: all tests pass.

- [ ] **Step 5: Lint + type check**

```bash
uv run ruff check src tests
uv run ty check src tests
```

- [ ] **Step 6: Commit**

```bash
git add src/cycling_agent/strava/poller.py tests/unit/strava/test_poller.py
git commit -m "feat(strava): add poller that detects new races and upserts to db"
```

---

### Task 9: Stats card renderer

**Files:**
- Create: `src/cycling_agent/media/__init__.py`
- Create: `src/cycling_agent/media/stats_card.py`
- Create: `tests/unit/media/__init__.py`
- Create: `tests/unit/media/test_stats_card.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/media/test_stats_card.py
"""Tests for the stats card renderer."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from PIL import Image

from cycling_agent.media.stats_card import StatsCardRenderer
from cycling_agent.strava.client import StravaActivity


def _activity() -> StravaActivity:
    return StravaActivity(
        id=1, name="Volta ao Algarve - Etapa 2", workout_type=11,
        started_at=dt.datetime(2026, 2, 19, 13, 30, tzinfo=dt.UTC),
        distance_m=158420, moving_time_s=12640, elevation_gain_m=1834,
        avg_speed_mps=12.5, avg_power_w=268, norm_power_w=305,
        avg_hr=162, max_hr=188, kilojoules=3387, feeling_text=None, polyline="abc",
    )


def test_render_creates_png_at_expected_path(tmp_path: Path) -> None:
    out = tmp_path / "card.png"
    StatsCardRenderer().render(_activity(), out)
    assert out.exists()
    img = Image.open(out)
    assert img.format == "PNG"


def test_render_dimensions_are_1080x1080(tmp_path: Path) -> None:
    out = tmp_path / "card.png"
    StatsCardRenderer().render(_activity(), out)
    assert Image.open(out).size == (1080, 1080)


def test_render_handles_missing_power(tmp_path: Path) -> None:
    out = tmp_path / "card.png"
    a = _activity()
    no_power = StravaActivity(**{**a.__dict__, "avg_power_w": None, "norm_power_w": None})
    StatsCardRenderer().render(no_power, out)
    assert out.exists()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/media/test_stats_card.py -v
```

Expected: import error.

- [ ] **Step 3: Implement the renderer**

```python
# src/cycling_agent/media/__init__.py
"""Media rendering utilities (stats cards, route maps)."""
```

```python
# src/cycling_agent/media/stats_card.py
"""Render a square stats card image for a Strava activity.

Pillow-based. Uses the default DejaVu font shipped with Pillow so the
renderer has no external font dependency.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from cycling_agent.strava.client import StravaActivity

_SIZE = (1080, 1080)
_BG = (15, 18, 26)
_FG = (240, 240, 245)
_ACCENT = (255, 130, 60)


class StatsCardRenderer:
    """Render a single 1080x1080 PNG stats card."""

    def render(self, activity: StravaActivity, out_path: Path) -> Path:
        img = Image.new("RGB", _SIZE, _BG)
        draw = ImageDraw.Draw(img)

        title_font = _font(64)
        body_font = _font(48)
        small_font = _font(32)

        draw.text((60, 60), activity.name[:36], font=title_font, fill=_FG)
        draw.text(
            (60, 140),
            activity.started_at.strftime("%d %b %Y"),
            font=small_font,
            fill=_ACCENT,
        )

        rows = _stat_rows(activity)
        y = 240
        for label, value in rows:
            draw.text((60, y), label, font=small_font, fill=_ACCENT)
            draw.text((60, y + 36), value, font=body_font, fill=_FG)
            y += 130

        out_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(out_path, "PNG")
        return out_path


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _stat_rows(a: StravaActivity) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    rows.append(("DISTANCE", f"{a.distance_m / 1000:.1f} km"))
    rows.append(("TIME", _fmt_duration(a.moving_time_s)))
    rows.append(("ELEVATION", f"{int(a.elevation_gain_m)} m"))
    if a.avg_power_w is not None:
        np = f" / NP {int(a.norm_power_w)} W" if a.norm_power_w else ""
        rows.append(("POWER", f"AVG {int(a.avg_power_w)} W{np}"))
    if a.avg_hr is not None:
        rows.append(("HEART RATE", f"AVG {int(a.avg_hr)} bpm"))
    return rows


def _fmt_duration(seconds: int) -> str:
    delta = dt.timedelta(seconds=seconds)
    h, rem = divmod(int(delta.total_seconds()), 3600)
    m, s = divmod(rem, 60)
    return f"{h}h {m:02d}m"
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/media/test_stats_card.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Lint + type check**

```bash
uv run ruff check src tests
uv run ty check src tests
```

- [ ] **Step 6: Commit**

```bash
git add src/cycling_agent/media tests/unit/media
git commit -m "feat(media): add Pillow stats card renderer"
```

---

### Task 10: Route map renderer

**Files:**
- Create: `src/cycling_agent/media/route_map.py`
- Create: `tests/unit/media/test_route_map.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/media/test_route_map.py
"""Tests for the route map renderer (no network: stubbed staticmaps)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

from cycling_agent.media.route_map import RouteMapRenderer


def test_render_writes_png(tmp_path: Path) -> None:
    out = tmp_path / "map.png"
    fake_ctx = MagicMock()
    fake_ctx.render_pillow.return_value = Image.new("RGB", (1080, 1080), (200, 200, 200))
    builder = MagicMock(return_value=fake_ctx)
    renderer = RouteMapRenderer(context_factory=builder)
    renderer.render(polyline="}~p_F~ngzAhIb@", out_path=out)
    assert out.exists()
    builder.assert_called_once()


def test_render_raises_on_empty_polyline(tmp_path: Path) -> None:
    renderer = RouteMapRenderer()
    with pytest.raises(ValueError, match="polyline"):
        renderer.render(polyline="", out_path=tmp_path / "x.png")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/media/test_route_map.py -v
```

Expected: import error.

- [ ] **Step 3: Implement the renderer**

```python
# src/cycling_agent/media/route_map.py
"""Render the activity route as a PNG using py-staticmaps.

Decodes the Strava `summary_polyline` and renders an OSM-tile background
with the route overlaid. Network is required at render time to fetch tiles
unless a custom context factory is injected (used in tests).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import polyline as polyline_lib  # bundled by stravalib's dependency tree
import staticmaps

_DEFAULT_SIZE = (1080, 1080)


def _default_context_factory() -> Any:
    ctx = staticmaps.Context()
    ctx.set_tile_provider(staticmaps.tile_provider_OSM)
    return ctx


class RouteMapRenderer:
    def __init__(self, context_factory: Callable[[], Any] = _default_context_factory) -> None:
        self._context_factory = context_factory

    def render(self, *, polyline: str, out_path: Path) -> Path:
        if not polyline:
            raise ValueError("polyline is empty; cannot render route map")
        coords = polyline_lib.decode(polyline)
        if not coords:
            raise ValueError("polyline decoded to no coordinates")

        ctx = self._context_factory()
        line = staticmaps.Line(
            [staticmaps.create_latlng(lat, lon) for lat, lon in coords],
            color=staticmaps.parse_color("#FF823C"),
            width=4,
        )
        ctx.add_object(line)
        img = ctx.render_pillow(*_DEFAULT_SIZE)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(out_path, "PNG")
        return out_path
```

Add the polyline dependency:

```bash
uv add polyline==2.0.2
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/media -v
```

Expected: all tests pass.

- [ ] **Step 5: Lint + type check**

```bash
uv run ruff check src tests
uv run ty check src tests
```

- [ ] **Step 6: Commit**

```bash
git add src/cycling_agent/media/route_map.py tests/unit/media/test_route_map.py pyproject.toml
git commit -m "feat(media): add staticmaps-based route map renderer"
```

---

### Task 11: Publisher protocol + Facebook publisher

**Files:**
- Create: `src/cycling_agent/publishers/__init__.py`
- Create: `src/cycling_agent/publishers/base.py`
- Create: `src/cycling_agent/publishers/facebook.py`
- Create: `tests/unit/publishers/__init__.py`
- Create: `tests/unit/publishers/test_facebook.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/publishers/test_facebook.py
"""Tests for the Facebook publisher."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cycling_agent.publishers.base import PublishRequest
from cycling_agent.publishers.facebook import FacebookPublisher


def _request(tmp_path: Path) -> PublishRequest:
    img = tmp_path / "card.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 50)
    return PublishRequest(
        caption="Race report\n#brandx",
        media_paths=[img],
    )


def test_publish_uploads_photo_with_caption(tmp_path: Path) -> None:
    fake_page = MagicMock()
    fake_page.create_photo.return_value = MagicMock(__getitem__=lambda self, k: "999_888")
    publisher = FacebookPublisher(page=fake_page, ig_business_id=None, dry_run=False)
    post_id = publisher.publish(_request(tmp_path))
    assert post_id == "999_888"
    fake_page.create_photo.assert_called_once()
    kwargs = fake_page.create_photo.call_args.kwargs
    assert kwargs["params"]["caption"] == "Race report\n#brandx"
    assert "source" in kwargs["files"]


def test_publish_dry_run_does_not_call_api(tmp_path: Path) -> None:
    fake_page = MagicMock()
    publisher = FacebookPublisher(page=fake_page, ig_business_id=None, dry_run=True)
    post_id = publisher.publish(_request(tmp_path))
    assert post_id.startswith("dry-run-fb-")
    fake_page.create_photo.assert_not_called()


def test_publish_raises_on_missing_media(tmp_path: Path) -> None:
    publisher = FacebookPublisher(page=MagicMock(), ig_business_id=None, dry_run=False)
    req = PublishRequest(caption="x", media_paths=[tmp_path / "nope.png"])
    with pytest.raises(FileNotFoundError):
        publisher.publish(req)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/publishers/test_facebook.py -v
```

Expected: import error.

- [ ] **Step 3: Implement the protocol and Facebook publisher**

```python
# src/cycling_agent/publishers/__init__.py
"""Social network publishers."""
```

```python
# src/cycling_agent/publishers/base.py
"""Common publisher protocol."""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol


@dataclasses.dataclass(frozen=True)
class PublishRequest:
    caption: str
    media_paths: Sequence[Path]


class Publisher(Protocol):
    """A publisher posts a draft to one platform and returns the external id."""

    def publish(self, request: PublishRequest) -> str: ...
```

```python
# src/cycling_agent/publishers/facebook.py
"""Facebook Page publisher using the facebook-business SDK."""

from __future__ import annotations

import secrets
from typing import Optional

import structlog

from cycling_agent.publishers.base import PublishRequest

log = structlog.get_logger(__name__)


class FacebookPublisher:
    """Posts photos with a caption to a Facebook Page.

    The ``page`` argument is a ``facebook_business.adobjects.page.Page`` instance
    or a mock with the same surface (``create_photo``).

    Note: ``ig_business_id`` is unused here but accepted for symmetry with how
    the Instagram publisher composes itself; allows both publishers to be built
    from the same factory.
    """

    def __init__(self, *, page: object, ig_business_id: Optional[str], dry_run: bool) -> None:
        self._page = page
        self._dry_run = dry_run
        self._ig_business_id = ig_business_id  # not used for FB

    def publish(self, request: PublishRequest) -> str:
        if self._dry_run:
            fake_id = f"dry-run-fb-{secrets.token_hex(4)}"
            log.info("publisher.fb.dry_run", caption_preview=request.caption[:80], id=fake_id)
            return fake_id

        if not request.media_paths:
            raise ValueError("Facebook publisher requires at least one media file")
        media = request.media_paths[0]
        if not media.exists():
            raise FileNotFoundError(media)

        with media.open("rb") as fh:
            response = self._page.create_photo(
                params={"caption": request.caption, "published": True},
                files={"source": fh},
            )
        post_id = str(response["id"])
        log.info("publisher.fb.published", id=post_id)
        return post_id
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/publishers/test_facebook.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Lint + type check**

```bash
uv run ruff check src tests
uv run ty check src tests
```

- [ ] **Step 6: Commit**

```bash
git add src/cycling_agent/publishers tests/unit/publishers
git commit -m "feat(publishers): add Publisher protocol and Facebook implementation"
```

---

### Task 12: Instagram publisher (FB album → image_url → IG container → publish)

**Files:**
- Create: `src/cycling_agent/publishers/instagram.py`
- Create: `tests/unit/publishers/test_instagram.py`

The IG flow per the spec §8.2 option A: upload the image to a private FB album to obtain a CDN URL, then create an IG media container pointing at that URL, then publish the container.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/publishers/test_instagram.py
"""Tests for the Instagram publisher."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cycling_agent.publishers.base import PublishRequest
from cycling_agent.publishers.instagram import InstagramPublisher


def _request(tmp_path: Path) -> PublishRequest:
    img = tmp_path / "card.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 50)
    return PublishRequest(caption="Hello", media_paths=[img])


def test_publish_executes_three_step_flow(tmp_path: Path) -> None:
    fake_page = MagicMock()
    # Step 1: upload to FB album returns a record with an "images[0].source" URL
    fake_page.create_photo.return_value = {
        "id": "5555",
        "images": [{"source": "https://scontent.fb.example/image.jpg"}],
    }
    fake_ig = MagicMock()
    fake_ig.create_media.return_value = {"id": "container-1"}
    fake_ig.publish_media.return_value = {"id": "ig-post-1"}

    publisher = InstagramPublisher(page=fake_page, ig=fake_ig, dry_run=False)
    post_id = publisher.publish(_request(tmp_path))
    assert post_id == "ig-post-1"

    fake_page.create_photo.assert_called_once()
    fb_kwargs = fake_page.create_photo.call_args.kwargs
    assert fb_kwargs["params"]["published"] is False  # private upload to get URL only

    fake_ig.create_media.assert_called_once_with(
        params={"image_url": "https://scontent.fb.example/image.jpg", "caption": "Hello"}
    )
    fake_ig.publish_media.assert_called_once_with(params={"creation_id": "container-1"})


def test_publish_dry_run_skips_api(tmp_path: Path) -> None:
    publisher = InstagramPublisher(page=MagicMock(), ig=MagicMock(), dry_run=True)
    post_id = publisher.publish(_request(tmp_path))
    assert post_id.startswith("dry-run-ig-")


def test_publish_raises_when_fb_upload_returns_no_url(tmp_path: Path) -> None:
    fake_page = MagicMock()
    fake_page.create_photo.return_value = {"id": "5555", "images": []}
    publisher = InstagramPublisher(page=fake_page, ig=MagicMock(), dry_run=False)
    with pytest.raises(RuntimeError, match="image url"):
        publisher.publish(_request(tmp_path))
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/publishers/test_instagram.py -v
```

Expected: import error.

- [ ] **Step 3: Implement the publisher**

```python
# src/cycling_agent/publishers/instagram.py
"""Instagram Business publisher.

Implements spec §8.2 option A: upload the image to a private FB album to
obtain a CDN URL, then create an IG media container pointing at that URL,
then publish the container.
"""

from __future__ import annotations

import secrets

import structlog

from cycling_agent.publishers.base import PublishRequest

log = structlog.get_logger(__name__)


class InstagramPublisher:
    """Publishes a single image + caption to Instagram Business via Graph API.

    Args:
        page: facebook_business Page object (used to upload the image privately).
        ig: facebook_business IGUser object for the linked Instagram account.
        dry_run: when True, returns a fake id and skips all API calls.
    """

    def __init__(self, *, page: object, ig: object, dry_run: bool) -> None:
        self._page = page
        self._ig = ig
        self._dry_run = dry_run

    def publish(self, request: PublishRequest) -> str:
        if self._dry_run:
            fake_id = f"dry-run-ig-{secrets.token_hex(4)}"
            log.info("publisher.ig.dry_run", caption_preview=request.caption[:80], id=fake_id)
            return fake_id

        if not request.media_paths:
            raise ValueError("Instagram publisher requires exactly one media file")
        media = request.media_paths[0]
        if not media.exists():
            raise FileNotFoundError(media)

        # Step 1: private upload to FB album to obtain a CDN URL
        with media.open("rb") as fh:
            fb_response = self._page.create_photo(
                params={"published": False},
                files={"source": fh},
            )
        images = fb_response.get("images", [])
        if not images or "source" not in images[0]:
            raise RuntimeError(
                "Facebook upload did not return an image url; cannot create IG container"
            )
        image_url = images[0]["source"]
        log.info("publisher.ig.image_uploaded", url=image_url)

        # Step 2: create the IG media container
        container = self._ig.create_media(
            params={"image_url": image_url, "caption": request.caption}
        )
        creation_id = container["id"]

        # Step 3: publish the container
        published = self._ig.publish_media(params={"creation_id": creation_id})
        post_id = str(published["id"])
        log.info("publisher.ig.published", id=post_id)
        return post_id
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/publishers -v
```

Expected: all tests pass.

- [ ] **Step 5: Lint + type check**

```bash
uv run ruff check src tests
uv run ty check src tests
```

- [ ] **Step 6: Commit**

```bash
git add src/cycling_agent/publishers/instagram.py tests/unit/publishers/test_instagram.py
git commit -m "feat(publishers): add Instagram publisher via FB-album image_url trick"
```

---


### Task 13: Telegram bot — send draft cards + handle button callbacks

**Files:**
- Create: `src/cycling_agent/approval/__init__.py`
- Create: `src/cycling_agent/approval/bot.py`
- Create: `tests/unit/approval/__init__.py`
- Create: `tests/unit/approval/test_bot.py`

The bot exposes two surfaces: `send_draft_card` (called by the agent's approval tool) and a set of handlers that respond to user actions. Each handler writes the result to the DB and logs an `ApprovalEvent`. Handlers are unit-tested by calling them directly with mocked PTB `Update` and `Context` objects — no real Telegram process is started in tests.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/approval/test_bot.py
"""Tests for the Telegram approval bot handlers."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from cycling_agent.approval.bot import (
    ApprovalBot,
    CB_APPROVE_NOW,
    CB_APPROVE_QUEUED,
    CB_REGENERATE,
    CB_REJECT,
    CB_RESCHEDULE,
    callback_data,
)
from cycling_agent.db.engine import build_engine, build_session_factory, init_schema
from cycling_agent.db.models import DraftStatus, Language, Platform
from cycling_agent.db.repo import Repository


@pytest.fixture()
def repo() -> Repository:
    engine = build_engine(":memory:")
    init_schema(engine)
    return Repository(build_session_factory(engine))


@pytest.fixture()
def seeded_draft(repo: Repository) -> int:
    repo.upsert_activity(id=1, started_at=dt.datetime(2026, 4, 1), name="Crit", workout_type=11)
    return repo.create_draft(
        activity_id=1, platform=Platform.FACEBOOK, language=Language.PT,
        caption="hello", hashtags=None, media_paths=None,
    )


def _query(callback_data_str: str) -> SimpleNamespace:
    """Build a minimal PTB CallbackQuery stub."""
    msg = SimpleNamespace(message_id=42, chat_id=11111)
    answer = AsyncMock()
    return SimpleNamespace(
        data=callback_data_str,
        answer=answer,
        message=msg,
        from_user=SimpleNamespace(id=11111),
        edit_message_reply_markup=AsyncMock(),
    )


def _update(query) -> SimpleNamespace:
    return SimpleNamespace(callback_query=query, effective_chat=SimpleNamespace(id=11111))


def _context() -> SimpleNamespace:
    bot = MagicMock()
    bot.send_message = AsyncMock()
    return SimpleNamespace(bot=bot, user_data={}, chat_data={})


async def test_callback_data_helpers_roundtrip() -> None:
    payload = callback_data(CB_APPROVE_QUEUED, draft_id=42)
    bot = ApprovalBot(repo=MagicMock(), chat_id=1)
    parsed = bot._parse_callback(payload)
    assert parsed == (CB_APPROVE_QUEUED, 42)


async def test_handle_approve_queued_sets_status(repo: Repository, seeded_draft: int) -> None:
    bot = ApprovalBot(repo=repo, chat_id=11111)
    update = _update(_query(callback_data(CB_APPROVE_QUEUED, draft_id=seeded_draft)))
    await bot.handle_callback(update, _context())
    d = repo.get_draft(seeded_draft)
    assert d is not None
    assert d.status == DraftStatus.APPROVED
    assert d.post_now is False


async def test_handle_approve_now_sets_post_now(repo: Repository, seeded_draft: int) -> None:
    bot = ApprovalBot(repo=repo, chat_id=11111)
    update = _update(_query(callback_data(CB_APPROVE_NOW, draft_id=seeded_draft)))
    await bot.handle_callback(update, _context())
    d = repo.get_draft(seeded_draft)
    assert d is not None
    assert d.status == DraftStatus.APPROVED
    assert d.post_now is True


async def test_handle_reject_marks_rejected(repo: Repository, seeded_draft: int) -> None:
    bot = ApprovalBot(repo=repo, chat_id=11111)
    update = _update(_query(callback_data(CB_REJECT, draft_id=seeded_draft)))
    await bot.handle_callback(update, _context())
    d = repo.get_draft(seeded_draft)
    assert d is not None
    assert d.status == DraftStatus.REJECTED


async def test_handle_regenerate_prompts_for_hint(repo: Repository, seeded_draft: int) -> None:
    bot = ApprovalBot(repo=repo, chat_id=11111)
    update = _update(_query(callback_data(CB_REGENERATE, draft_id=seeded_draft)))
    ctx = _context()
    await bot.handle_callback(update, ctx)
    d = repo.get_draft(seeded_draft)
    assert d is not None
    assert d.status == DraftStatus.REGENERATING
    ctx.bot.send_message.assert_awaited()
    assert ctx.user_data.get("awaiting_hint_for") == seeded_draft


async def test_handle_text_message_after_regenerate_records_hint(
    repo: Repository, seeded_draft: int
) -> None:
    bot = ApprovalBot(repo=repo, chat_id=11111)
    repo.set_draft_status(seeded_draft, DraftStatus.REGENERATING)

    ctx = _context()
    ctx.user_data["awaiting_hint_for"] = seeded_draft
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=11111),
        message=SimpleNamespace(text="more grateful, less hype", reply_text=AsyncMock()),
    )
    await bot.handle_text(update, ctx)

    d = repo.get_draft(seeded_draft)
    assert d is not None
    assert d.feedback_hint == "more grateful, less hype"
    assert "awaiting_hint_for" not in ctx.user_data


async def test_handle_reschedule_prompts_for_time(
    repo: Repository, seeded_draft: int
) -> None:
    repo.set_approved(seeded_draft, post_now=False)
    repo.schedule_draft(seeded_draft, dt.datetime(2026, 4, 1, 19, 0))
    bot = ApprovalBot(repo=repo, chat_id=11111)
    update = _update(_query(callback_data(CB_RESCHEDULE, draft_id=seeded_draft)))
    ctx = _context()
    await bot.handle_callback(update, ctx)
    assert ctx.user_data.get("awaiting_reschedule_for") == seeded_draft
    ctx.bot.send_message.assert_awaited()


async def test_handle_text_after_reschedule_updates_scheduled_for(
    repo: Repository, seeded_draft: int
) -> None:
    repo.set_approved(seeded_draft, post_now=False)
    repo.schedule_draft(seeded_draft, dt.datetime(2026, 4, 1, 19, 0))
    bot = ApprovalBot(repo=repo, chat_id=11111)
    ctx = _context()
    ctx.user_data["awaiting_reschedule_for"] = seeded_draft
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=11111),
        message=SimpleNamespace(text="2026-04-02 21:00", reply_text=AsyncMock()),
    )
    await bot.handle_text(update, ctx)
    d = repo.get_draft(seeded_draft)
    assert d is not None
    assert d.scheduled_for == dt.datetime(2026, 4, 2, 21, 0)


async def test_handle_callback_ignores_other_chats(
    repo: Repository, seeded_draft: int
) -> None:
    bot = ApprovalBot(repo=repo, chat_id=99999)
    update = SimpleNamespace(
        callback_query=_query(callback_data(CB_APPROVE_QUEUED, draft_id=seeded_draft)),
        effective_chat=SimpleNamespace(id=11111),
    )
    await bot.handle_callback(update, _context())
    d = repo.get_draft(seeded_draft)
    assert d is not None
    assert d.status != DraftStatus.APPROVED


async def test_send_draft_card_calls_telegram_with_buttons(
    repo: Repository, seeded_draft: int, tmp_path: Path
) -> None:
    img = tmp_path / "card.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 50)

    fake_bot = MagicMock()
    fake_bot.send_photo = AsyncMock(return_value=SimpleNamespace(message_id=4242))
    bot = ApprovalBot(repo=repo, chat_id=11111, telegram_bot=fake_bot)

    msg_id = await bot.send_draft_card(
        draft_id=seeded_draft, caption="hello", media_paths=[img]
    )
    assert msg_id == 4242
    fake_bot.send_photo.assert_awaited_once()
    kwargs = fake_bot.send_photo.await_args.kwargs
    assert kwargs["chat_id"] == 11111
    assert "reply_markup" in kwargs
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/approval/test_bot.py -v
```

Expected: import error.

- [ ] **Step 3: Implement the bot module**

```python
# src/cycling_agent/approval/__init__.py
"""Telegram approval bot."""
```

```python
# src/cycling_agent/approval/bot.py
"""Telegram approval bot.

Exposes:
- ``send_draft_card``: posts a draft preview to the rider's chat with action buttons.
- ``handle_callback`` / ``handle_text``: handlers for button presses and follow-up
  text replies (edit text, regenerate hint, reschedule time).

The bot writes user actions to the DB. The agent loop reads them on the next
cycle. There is no in-memory waiting between bot and agent.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Optional

import dateparser
import structlog
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from cycling_agent.db.models import DraftStatus
from cycling_agent.db.repo import Repository

log = structlog.get_logger(__name__)

# Callback data prefixes (kept short — Telegram limits callback_data to 64 bytes).
CB_APPROVE_QUEUED = "aq"
CB_APPROVE_NOW = "an"
CB_EDIT = "ed"
CB_REGENERATE = "rg"
CB_REJECT = "rj"
CB_RESCHEDULE = "rs"


def callback_data(action: str, *, draft_id: int) -> str:
    return f"{action}:{draft_id}"


class ApprovalBot:
    """Stateless wrapper over python-telegram-bot for the cycling agent."""

    def __init__(
        self,
        *,
        repo: Repository,
        chat_id: int,
        telegram_bot: Optional[Any] = None,
    ) -> None:
        self._repo = repo
        self._chat_id = chat_id
        self._bot = telegram_bot  # set by register_handlers when running in app

    # --- public API -----------------------------------------------------------

    def register_handlers(self, application: Application) -> None:
        """Wire handlers into a python-telegram-bot Application."""
        self._bot = application.bot
        application.add_handler(CommandHandler("start", self._handle_start))
        application.add_handler(CallbackQueryHandler(self.handle_callback))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))
        application.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))

    async def send_draft_card(
        self,
        *,
        draft_id: int,
        caption: str,
        media_paths: Sequence[Path],
    ) -> int:
        """Post a draft preview to the rider's chat, return the telegram message id."""
        if self._bot is None:
            raise RuntimeError("ApprovalBot.send_draft_card requires a telegram bot")

        markup = self._build_keyboard(draft_id, include_reschedule=False)
        media = next((p for p in media_paths if p.exists()), None)
        if media is None:
            sent = await self._bot.send_message(
                chat_id=self._chat_id, text=caption, reply_markup=markup
            )
        else:
            with media.open("rb") as fh:
                sent = await self._bot.send_photo(
                    chat_id=self._chat_id, photo=fh, caption=caption, reply_markup=markup
                )
        return int(sent.message_id)

    # --- handlers -------------------------------------------------------------

    async def _handle_start(
        self, update: Any, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        await update.message.reply_text("cycling-agent ready. I'll send you race posts to approve.")

    async def handle_callback(
        self, update: Any, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        chat_id = getattr(update.effective_chat, "id", None)
        if chat_id != self._chat_id:
            log.warning("approval.bot.foreign_chat", chat_id=chat_id)
            return

        query = update.callback_query
        try:
            action, draft_id = self._parse_callback(query.data)
        except ValueError:
            await query.answer("bad callback")
            return

        await query.answer()  # acknowledges to Telegram immediately

        if action == CB_APPROVE_QUEUED:
            self._repo.set_approved(draft_id, post_now=False)
            self._repo.log_approval_event(
                draft_id=draft_id, event="approved",
                payload=json.dumps({"post_now": False}),
            )
            await context.bot.send_message(
                chat_id=self._chat_id, text=f"Draft #{draft_id} approved — queued for next publish window.",
            )

        elif action == CB_APPROVE_NOW:
            self._repo.set_approved(draft_id, post_now=True)
            self._repo.log_approval_event(
                draft_id=draft_id, event="approved",
                payload=json.dumps({"post_now": True}),
            )
            await context.bot.send_message(
                chat_id=self._chat_id, text=f"Draft #{draft_id} approved — posting now.",
            )

        elif action == CB_REJECT:
            self._repo.set_draft_status(draft_id, DraftStatus.REJECTED)
            self._repo.log_approval_event(draft_id=draft_id, event="rejected", payload="{}")
            await context.bot.send_message(
                chat_id=self._chat_id, text=f"Draft #{draft_id} rejected.",
            )

        elif action == CB_REGENERATE:
            self._repo.set_draft_status(draft_id, DraftStatus.REGENERATING)
            context.user_data["awaiting_hint_for"] = draft_id
            await context.bot.send_message(
                chat_id=self._chat_id,
                text=f"Send an optional hint for the regenerated draft #{draft_id} (e.g. 'more grateful, less hype'). Send 'skip' to regenerate without a hint.",
            )

        elif action == CB_EDIT:
            self._repo.set_draft_status(draft_id, DraftStatus.EDITING)
            context.user_data["awaiting_edit_for"] = draft_id
            await context.bot.send_message(
                chat_id=self._chat_id,
                text=f"Send the replacement caption for draft #{draft_id}.",
            )

        elif action == CB_RESCHEDULE:
            context.user_data["awaiting_reschedule_for"] = draft_id
            await context.bot.send_message(
                chat_id=self._chat_id,
                text=f"Send a new time for draft #{draft_id} (e.g. '2026-04-02 21:00' or 'tomorrow 19:00').",
            )

    async def handle_text(
        self, update: Any, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        chat_id = getattr(update.effective_chat, "id", None)
        if chat_id != self._chat_id:
            return

        text = (update.message.text or "").strip()

        edit_for = context.user_data.pop("awaiting_edit_for", None)
        if edit_for is not None:
            self._repo.set_draft_status(
                int(edit_for), DraftStatus.AWAITING_APPROVAL, caption=text
            )
            self._repo.log_approval_event(
                draft_id=int(edit_for), event="edited",
                payload=json.dumps({"new_caption": text}),
            )
            await update.message.reply_text(f"Draft #{edit_for} updated. Tap Approve to publish.")
            return

        hint_for = context.user_data.pop("awaiting_hint_for", None)
        if hint_for is not None:
            hint = "" if text.lower() == "skip" else text
            self._repo.set_draft_status(int(hint_for), DraftStatus.REGENERATING, feedback_hint=hint)
            self._repo.log_approval_event(
                draft_id=int(hint_for), event="regenerated",
                payload=json.dumps({"hint": hint}),
            )
            await update.message.reply_text(
                f"Hint recorded for draft #{hint_for}. Will regenerate on next cycle."
            )
            return

        resched_for = context.user_data.pop("awaiting_reschedule_for", None)
        if resched_for is not None:
            parsed = dateparser.parse(text, settings={"PREFER_DATES_FROM": "future"})
            if parsed is None:
                await update.message.reply_text(
                    f"Could not parse '{text}' as a date. Try '2026-04-02 21:00'."
                )
                context.user_data["awaiting_reschedule_for"] = resched_for
                return
            self._repo.reschedule_draft(int(resched_for), parsed)
            self._repo.log_approval_event(
                draft_id=int(resched_for), event="rescheduled",
                payload=json.dumps({"scheduled_for": parsed.isoformat()}),
            )
            await update.message.reply_text(
                f"Draft #{resched_for} rescheduled to {parsed.isoformat(timespec='minutes')}."
            )
            return

    async def handle_photo(
        self, update: Any, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        # Photo attach for an upcoming approval; lands in v1.5. For now: acknowledge.
        await update.message.reply_text(
            "Photo received — attaching photos to drafts will be supported in a follow-up."
        )

    # --- helpers --------------------------------------------------------------

    def _parse_callback(self, data: str) -> tuple[str, int]:
        action, _, draft_id_str = data.partition(":")
        if not action or not draft_id_str:
            raise ValueError(f"bad callback data: {data!r}")
        return action, int(draft_id_str)

    def _build_keyboard(
        self, draft_id: int, *, include_reschedule: bool
    ) -> InlineKeyboardMarkup:
        rows = [
            [
                InlineKeyboardButton("Approve (queued)", callback_data=callback_data(CB_APPROVE_QUEUED, draft_id=draft_id)),
                InlineKeyboardButton("Approve & post now", callback_data=callback_data(CB_APPROVE_NOW, draft_id=draft_id)),
            ],
            [
                InlineKeyboardButton("Edit", callback_data=callback_data(CB_EDIT, draft_id=draft_id)),
                InlineKeyboardButton("Regenerate", callback_data=callback_data(CB_REGENERATE, draft_id=draft_id)),
                InlineKeyboardButton("Reject", callback_data=callback_data(CB_REJECT, draft_id=draft_id)),
            ],
        ]
        if include_reschedule:
            rows.append(
                [InlineKeyboardButton("Reschedule", callback_data=callback_data(CB_RESCHEDULE, draft_id=draft_id))]
            )
        return InlineKeyboardMarkup(rows)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/approval -v
```

Expected: all tests pass.

- [ ] **Step 5: Lint + type check**

```bash
uv run ruff check src tests
uv run ty check src tests
```

- [ ] **Step 6: Commit**

```bash
git add src/cycling_agent/approval tests/unit/approval
git commit -m "feat(approval): add Telegram bot with DB-mediated approval state"
```

---


## Phase 4 — Agent tools

Tools follow the LangChain `@tool` convention. Each tool module exposes a `build_*_tools(deps)` factory that returns a list of bound tools ready to register with the deep agent. This avoids global state and keeps tools test-friendly.

### Task 14: Strava, content, and media tools

**Files:**
- Create: `src/cycling_agent/agent/__init__.py`
- Create: `src/cycling_agent/agent/tools/__init__.py`
- Create: `src/cycling_agent/agent/tools/strava_tools.py`
- Create: `src/cycling_agent/agent/tools/content_tools.py`
- Create: `src/cycling_agent/agent/tools/media_tools.py`
- Create: `tests/unit/agent/__init__.py`
- Create: `tests/unit/agent/tools/__init__.py`
- Create: `tests/unit/agent/tools/test_basic_tools.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/agent/tools/test_basic_tools.py
"""Tests for the data-fetch tool builders."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cycling_agent.agent.tools.content_tools import build_content_tools
from cycling_agent.agent.tools.media_tools import build_media_tools
from cycling_agent.agent.tools.strava_tools import build_strava_tools
from cycling_agent.db.engine import build_engine, build_session_factory, init_schema
from cycling_agent.db.models import ActivityStatus, Language, Sponsor, StyleExample
from cycling_agent.db.repo import Repository
from cycling_agent.strava.client import StravaActivity


@pytest.fixture()
def repo() -> Repository:
    engine = build_engine(":memory:")
    init_schema(engine)
    return Repository(build_session_factory(engine))


def _activity(id_: int = 1) -> StravaActivity:
    return StravaActivity(
        id=id_, name=f"Race {id_}", workout_type=11,
        started_at=dt.datetime(2026, 4, 1, 10, 0, tzinfo=dt.UTC),
        distance_m=158420, moving_time_s=12640, elevation_gain_m=1834,
        avg_speed_mps=12.5, avg_power_w=268, norm_power_w=305,
        avg_hr=162, max_hr=188, kilojoules=3387, feeling_text=None, polyline="abc",
    )


def test_list_new_races_returns_unprocessed(repo: Repository) -> None:
    repo.upsert_activity(id=1, started_at=dt.datetime(2026, 4, 1), name="Race", workout_type=11)
    fake_strava = MagicMock()
    poller = MagicMock()
    poller.poll.return_value = [1]
    tools = build_strava_tools(repo=repo, client=fake_strava, poller=poller)
    list_new = next(t for t in tools if t.name == "list_new_races")
    result = list_new.invoke({})
    assert "1" in result


def test_get_activity_detail_returns_summary_fields(repo: Repository) -> None:
    fake_strava = MagicMock()
    fake_strava.get_activity_detail.return_value = _activity()
    poller = MagicMock()
    tools = build_strava_tools(repo=repo, client=fake_strava, poller=poller)
    get_detail = next(t for t in tools if t.name == "get_activity_detail")
    result = get_detail.invoke({"activity_id": 1})
    assert "158.4 km" in result or "158.42" in result
    assert "Race 1" in result


def test_get_feeling_returns_stored_text(repo: Repository) -> None:
    repo.upsert_activity(id=1, started_at=dt.datetime(2026, 4, 1), name="Race", workout_type=11)
    repo.set_feeling_text(activity_id=1, text="rainy crit, top 20")
    tools = build_strava_tools(repo=repo, client=MagicMock(), poller=MagicMock())
    get_feeling = next(t for t in tools if t.name == "get_feeling")
    result = get_feeling.invoke({"activity_id": 1})
    assert "rainy crit" in result


def test_read_sponsors_returns_all(repo: Repository) -> None:
    repo.replace_sponsors([
        Sponsor(name="A", handle_facebook="@a", handle_instagram="@a", hashtag="#a"),
        Sponsor(name="B", handle_facebook="@b", handle_instagram="@b", hashtag="#b"),
    ])
    tools = build_content_tools(repo=repo)
    read_sponsors = next(t for t in tools if t.name == "read_sponsors")
    result = read_sponsors.invoke({})
    assert "A" in result and "B" in result


def test_read_style_examples_filtered_by_language(repo: Repository) -> None:
    repo.replace_style_examples([
        StyleExample(language=Language.PT, text="Texto em PT"),
        StyleExample(language=Language.EN, text="Text in EN"),
    ])
    tools = build_content_tools(repo=repo)
    read_style = next(t for t in tools if t.name == "read_style_examples")
    result = read_style.invoke({"language": "pt"})
    assert "PT" in result
    assert "EN" not in result


def test_render_stats_card_writes_file(repo: Repository, tmp_path: Path) -> None:
    fake_strava = MagicMock()
    fake_strava.get_activity_detail.return_value = _activity()
    media_dir = tmp_path / "media"
    tools = build_media_tools(repo=repo, strava=fake_strava, media_dir=media_dir)
    render = next(t for t in tools if t.name == "render_stats_card")
    out_path_str = render.invoke({"activity_id": 1})
    assert Path(out_path_str).exists()
    assert Path(out_path_str).suffix == ".png"


def test_render_route_map_writes_file(repo: Repository, tmp_path: Path) -> None:
    fake_strava = MagicMock()
    fake_strava.get_activity_detail.return_value = _activity()
    media_dir = tmp_path / "media"
    # Stub the renderer so we don't hit the network for tiles.
    from cycling_agent.media.route_map import RouteMapRenderer
    real = RouteMapRenderer.render
    def stub_render(self, *, polyline: str, out_path: Path) -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 50)
        return out_path
    RouteMapRenderer.render = stub_render  # type: ignore[method-assign]
    try:
        tools = build_media_tools(repo=repo, strava=fake_strava, media_dir=media_dir)
        render = next(t for t in tools if t.name == "render_route_map")
        out_path_str = render.invoke({"activity_id": 1})
        assert Path(out_path_str).exists()
    finally:
        RouteMapRenderer.render = real  # type: ignore[method-assign]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/agent/tools/test_basic_tools.py -v
```

Expected: import error.

- [ ] **Step 3: Implement the tool builders**

```python
# src/cycling_agent/agent/__init__.py
"""Agent layer (tools, sub-agents, orchestrator)."""
```

```python
# src/cycling_agent/agent/tools/__init__.py
"""LangChain tools for the cycling agent."""
```

```python
# src/cycling_agent/agent/tools/strava_tools.py
"""Tools the agent uses to interact with Strava and the activities table."""

from __future__ import annotations

import datetime as dt

from langchain_core.tools import BaseTool, tool

from cycling_agent.db.repo import Repository
from cycling_agent.strava.client import StravaClient
from cycling_agent.strava.poller import StravaPoller


def build_strava_tools(
    *, repo: Repository, client: StravaClient, poller: StravaPoller
) -> list[BaseTool]:
    """Build the Strava-related tools as bound LangChain tools."""

    @tool
    def list_new_races() -> str:
        """Return the ids of race activities not yet fully processed.

        Polls Strava once for any new activities, then returns ids of all
        activities currently in non-terminal states.
        """
        new = poller.poll(now=dt.datetime.now(dt.UTC))
        from cycling_agent.db.models import ActivityStatus

        in_flight = repo.list_activities_in_states(
            [ActivityStatus.DETECTED, ActivityStatus.DRAFTING, ActivityStatus.AWAITING_APPROVAL]
        )
        ids = sorted({a.id for a in in_flight} | set(new))
        if not ids:
            return "No races to process."
        return "Activity ids: " + ", ".join(str(i) for i in ids)

    @tool
    def get_activity_detail(activity_id: int) -> str:
        """Fetch full Strava detail for an activity and persist the feeling text."""
        a = client.get_activity_detail(activity_id)
        if a.feeling_text:
            repo.set_feeling_text(activity_id=a.id, text=a.feeling_text)
        return (
            f"Name: {a.name}\n"
            f"Started: {a.started_at.isoformat()}\n"
            f"Distance: {a.distance_m / 1000:.1f} km\n"
            f"Moving time: {a.moving_time_s // 60} min\n"
            f"Elevation: {int(a.elevation_gain_m)} m\n"
            f"Avg power: {a.avg_power_w} W\n"
            f"Norm power: {a.norm_power_w} W\n"
            f"Avg HR: {a.avg_hr} bpm\n"
            f"Max HR: {a.max_hr} bpm\n"
            f"Feeling: {a.feeling_text or '(none)'}"
        )

    @tool
    def get_feeling(activity_id: int) -> str:
        """Return the rider's private 'feeling' note for the activity, or empty."""
        a = repo.get_activity(activity_id)
        if a is None:
            return f"Activity {activity_id} not found."
        return a.feeling_text or "(no feeling text recorded)"

    return [list_new_races, get_activity_detail, get_feeling]
```

```python
# src/cycling_agent/agent/tools/content_tools.py
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

        ``language`` must be 'pt' or 'en'.
        """
        try:
            lang = Language(language)
        except ValueError as e:
            raise ValueError(f"language must be 'pt' or 'en', got {language!r}") from e
        examples = repo.list_style_examples(lang)
        if not examples:
            return f"No style examples for {language}."
        return "\n\n---\n\n".join(e.text for e in examples)

    return [read_sponsors, read_style_examples]
```

```python
# src/cycling_agent/agent/tools/media_tools.py
"""Media rendering tools."""

from __future__ import annotations

from pathlib import Path

from langchain_core.tools import BaseTool, tool

from cycling_agent.db.repo import Repository
from cycling_agent.media.route_map import RouteMapRenderer
from cycling_agent.media.stats_card import StatsCardRenderer
from cycling_agent.strava.client import StravaClient


def build_media_tools(
    *, repo: Repository, strava: StravaClient, media_dir: Path
) -> list[BaseTool]:
    stats_card = StatsCardRenderer()
    route_map = RouteMapRenderer()

    def _path(activity_id: int, kind: str) -> Path:
        out_dir = media_dir / str(activity_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir / f"{kind}.png"

    @tool
    def render_stats_card(activity_id: int) -> str:
        """Render a stats card PNG for an activity. Returns the file path."""
        a = strava.get_activity_detail(activity_id)
        path = _path(activity_id, "stats")
        stats_card.render(a, path)
        return str(path)

    @tool
    def render_route_map(activity_id: int) -> str:
        """Render a route map PNG for an activity. Returns the file path."""
        a = strava.get_activity_detail(activity_id)
        if not a.polyline:
            raise ValueError(f"activity {activity_id} has no polyline")
        path = _path(activity_id, "map")
        route_map.render(polyline=a.polyline, out_path=path)
        return str(path)

    return [render_stats_card, render_route_map]
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/agent/tools/test_basic_tools.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Lint + type check**

```bash
uv run ruff check src tests
uv run ty check src tests
```

- [ ] **Step 6: Commit**

```bash
git add src/cycling_agent/agent tests/unit/agent
git commit -m "feat(tools): add strava, content, and media tools"
```

---

### Task 15: Approval tools (with sponsor invariant)

**Files:**
- Create: `src/cycling_agent/agent/tools/approval_tools.py`
- Create: `tests/unit/agent/tools/test_approval_tools.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/agent/tools/test_approval_tools.py
"""Tests for approval tools (send_for_approval + check_approval_status)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from cycling_agent.agent.tools.approval_tools import build_approval_tools
from cycling_agent.db.engine import build_engine, build_session_factory, init_schema
from cycling_agent.db.models import DraftStatus, Language, Platform, Sponsor
from cycling_agent.db.repo import Repository


@pytest.fixture()
def repo() -> Repository:
    engine = build_engine(":memory:")
    init_schema(engine)
    repo = Repository(build_session_factory(engine))
    repo.upsert_activity(id=1, started_at=dt.datetime(2026, 4, 1), name="Crit", workout_type=11)
    repo.replace_sponsors(
        [
            Sponsor(name="BrandX", handle_facebook="@brandx", handle_instagram="@brandx", hashtag="#brandx"),
            Sponsor(name="BrandY", handle_facebook="@brandy", handle_instagram="@brandy", hashtag="#brandy"),
        ]
    )
    return repo


@pytest.fixture()
def fake_bot() -> MagicMock:
    bot = MagicMock()
    bot.send_draft_card = AsyncMock(return_value=4242)
    return bot


def test_send_for_approval_rejects_when_sponsor_missing(
    repo: Repository, fake_bot: MagicMock, tmp_path: Path
) -> None:
    img = tmp_path / "card.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 50)

    tools = build_approval_tools(repo=repo, bot=fake_bot)
    send_for_approval = next(t for t in tools if t.name == "send_for_approval")

    result = send_for_approval.invoke(
        {
            "activity_id": 1,
            "platform": "facebook",
            "language": "pt",
            "caption": "Hello, mentions only @brandx #brandx",  # missing @brandy #brandy
            "hashtags": "",
            "media_paths": str(img),
        }
    )
    assert "missing" in result.lower()
    fake_bot.send_draft_card.assert_not_called()


def test_send_for_approval_creates_draft_and_sends(
    repo: Repository, fake_bot: MagicMock, tmp_path: Path
) -> None:
    img = tmp_path / "card.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 50)

    caption = "Hello @brandx @brandy #brandx #brandy"
    tools = build_approval_tools(repo=repo, bot=fake_bot)
    send_for_approval = next(t for t in tools if t.name == "send_for_approval")
    result = send_for_approval.invoke(
        {
            "activity_id": 1,
            "platform": "facebook",
            "language": "pt",
            "caption": caption,
            "hashtags": "",
            "media_paths": str(img),
        }
    )
    assert "Sent" in result
    fake_bot.send_draft_card.assert_awaited_once()

    drafts = repo.list_drafts_in_states([DraftStatus.AWAITING_APPROVAL])
    assert len(drafts) == 1
    assert drafts[0].telegram_message_id == 4242


def test_check_approval_status_returns_pending(repo: Repository, fake_bot: MagicMock) -> None:
    did = repo.create_draft(
        activity_id=1, platform=Platform.FACEBOOK, language=Language.PT, caption="x",
    )
    repo.set_draft_status(did, DraftStatus.AWAITING_APPROVAL, telegram_message_id=42)
    tools = build_approval_tools(repo=repo, bot=fake_bot)
    check = next(t for t in tools if t.name == "check_approval_status")
    result = check.invoke({"draft_id": did})
    assert "pending" in result.lower()


def test_check_approval_status_returns_approved_with_post_now(
    repo: Repository, fake_bot: MagicMock
) -> None:
    did = repo.create_draft(
        activity_id=1, platform=Platform.FACEBOOK, language=Language.PT, caption="x",
    )
    repo.set_approved(did, post_now=True)
    tools = build_approval_tools(repo=repo, bot=fake_bot)
    check = next(t for t in tools if t.name == "check_approval_status")
    result = check.invoke({"draft_id": did})
    assert "approved" in result.lower()
    assert "post_now=true" in result.lower()


def test_check_approval_status_returns_regenerate_hint(
    repo: Repository, fake_bot: MagicMock
) -> None:
    did = repo.create_draft(
        activity_id=1, platform=Platform.FACEBOOK, language=Language.PT, caption="x",
    )
    repo.set_draft_status(did, DraftStatus.REGENERATING, feedback_hint="more grateful")
    tools = build_approval_tools(repo=repo, bot=fake_bot)
    check = next(t for t in tools if t.name == "check_approval_status")
    result = check.invoke({"draft_id": did})
    assert "regenerate" in result.lower()
    assert "more grateful" in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/agent/tools/test_approval_tools.py -v
```

Expected: import error.

- [ ] **Step 3: Implement approval tools**

```python
# src/cycling_agent/agent/tools/approval_tools.py
"""Approval-related tools.

Enforces the sponsor-presence invariant in ``send_for_approval``.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from langchain_core.tools import BaseTool, tool

from cycling_agent.approval.bot import ApprovalBot
from cycling_agent.db.models import DraftStatus, Language, Platform
from cycling_agent.db.repo import Repository


def build_approval_tools(*, repo: Repository, bot: ApprovalBot) -> list[BaseTool]:
    @tool
    def send_for_approval(
        activity_id: int,
        platform: str,
        language: str,
        caption: str,
        hashtags: str,
        media_paths: str,
    ) -> str:
        """Send a draft preview to Telegram for the rider to approve.

        Refuses if any sponsor handle/hashtag is missing from the caption +
        hashtags. ``media_paths`` is comma-separated file paths.
        Returns a status string. The caller should NOT block waiting for
        approval — call ``check_approval_status`` on subsequent cycles.
        """
        sponsors = repo.list_sponsors()
        platform_enum = Platform(platform)
        full_text = f"{caption}\n{hashtags}"
        missing = []
        for s in sponsors:
            handle = s.handle_facebook if platform_enum == Platform.FACEBOOK else s.handle_instagram
            tokens_required = [t for t in [handle, s.hashtag] if t]
            if not any(t in full_text for t in tokens_required):
                missing.append(s.name)
        if missing:
            return (
                f"REJECTED: missing sponsor mentions for: {', '.join(missing)}. "
                f"Re-draft to include each sponsor's handle or hashtag."
            )

        media_list = [Path(p.strip()) for p in media_paths.split(",") if p.strip()]
        draft_id = repo.create_draft(
            activity_id=activity_id,
            platform=platform_enum,
            language=Language(language),
            caption=caption,
            hashtags=hashtags or None,
            media_paths=",".join(str(p) for p in media_list) or None,
        )

        message_id = asyncio.run(
            bot.send_draft_card(
                draft_id=draft_id,
                caption=f"#{draft_id} ({platform}/{language})\n\n{caption}\n{hashtags}".strip(),
                media_paths=media_list,
            )
        )
        repo.set_draft_status(
            draft_id, DraftStatus.AWAITING_APPROVAL, telegram_message_id=message_id
        )
        return f"Sent draft #{draft_id} for approval (telegram message {message_id})."

    @tool
    def check_approval_status(draft_id: int) -> str:
        """Return the current approval status for a draft.

        Possible values: pending, approved (with post_now flag), edited (with new
        caption), regenerating (with hint), rejected.
        """
        d = repo.get_draft(draft_id)
        if d is None:
            return f"Draft {draft_id} not found."
        if d.status == DraftStatus.AWAITING_APPROVAL:
            return f"Draft {draft_id} status: pending"
        if d.status == DraftStatus.APPROVED:
            return f"Draft {draft_id} status: approved post_now={'true' if d.post_now else 'false'}"
        if d.status == DraftStatus.EDITING:
            return f"Draft {draft_id} status: editing (rider is composing replacement)"
        if d.status == DraftStatus.REGENERATING:
            hint = d.feedback_hint or ""
            return f"Draft {draft_id} status: regenerate hint={hint!r}"
        if d.status == DraftStatus.REJECTED:
            return f"Draft {draft_id} status: rejected"
        if d.status == DraftStatus.SCHEDULED:
            return f"Draft {draft_id} status: scheduled scheduled_for={d.scheduled_for}"
        if d.status == DraftStatus.PUBLISHED:
            return f"Draft {draft_id} status: published"
        return f"Draft {draft_id} status: {d.status.value}"

    return [send_for_approval, check_approval_status]
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/agent/tools/test_approval_tools.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Lint + type check**

```bash
uv run ruff check src tests
uv run ty check src tests
```

- [ ] **Step 6: Commit**

```bash
git add src/cycling_agent/agent/tools/approval_tools.py tests/unit/agent/tools/test_approval_tools.py
git commit -m "feat(tools): add approval tools with sponsor-presence invariant"
```

---

### Task 16: Publish tools (schedule + publish_due + publish_to_*)

**Files:**
- Create: `src/cycling_agent/agent/tools/publish_tools.py`
- Create: `tests/unit/agent/tools/test_publish_tools.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/agent/tools/test_publish_tools.py
"""Tests for publish-related agent tools."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from freezegun import freeze_time

from cycling_agent.agent.tools.publish_tools import build_publish_tools
from cycling_agent.db.engine import build_engine, build_session_factory, init_schema
from cycling_agent.db.models import DraftStatus, Language, Platform
from cycling_agent.db.repo import Repository


@pytest.fixture()
def repo() -> Repository:
    engine = build_engine(":memory:")
    init_schema(engine)
    repo = Repository(build_session_factory(engine))
    repo.upsert_activity(id=1, started_at=dt.datetime(2026, 4, 1), name="Crit", workout_type=11)
    return repo


def _approved_draft(repo: Repository, *, platform: Platform = Platform.FACEBOOK) -> int:
    did = repo.create_draft(
        activity_id=1, platform=platform, language=Language.PT,
        caption="x", media_paths="/tmp/a.png",
    )
    repo.set_approved(did, post_now=False)
    return did


def test_schedule_publish_sets_scheduled_for_today_when_in_future(repo: Repository) -> None:
    did = _approved_draft(repo)
    publishers = {Platform.FACEBOOK: MagicMock(), Platform.INSTAGRAM: MagicMock()}
    tools = build_publish_tools(
        repo=repo,
        publishers=publishers,
        publish_time_local="19:00",
        publish_timezone="Europe/Lisbon",
    )
    schedule = next(t for t in tools if t.name == "schedule_publish")
    with freeze_time("2026-04-01 10:00:00", tz_offset=0):
        result = schedule.invoke({"draft_id": did})
    assert "scheduled" in result.lower()
    d = repo.get_draft(did)
    assert d is not None
    assert d.status == DraftStatus.SCHEDULED
    assert d.scheduled_for is not None
    assert d.scheduled_for.hour == 19  # local Lisbon time same as UTC in summer-ish; verify field set


def test_schedule_publish_rolls_to_next_day_when_window_passed(repo: Repository) -> None:
    did = _approved_draft(repo)
    publishers = {Platform.FACEBOOK: MagicMock(), Platform.INSTAGRAM: MagicMock()}
    tools = build_publish_tools(
        repo=repo, publishers=publishers,
        publish_time_local="19:00", publish_timezone="Europe/Lisbon",
    )
    schedule = next(t for t in tools if t.name == "schedule_publish")
    with freeze_time("2026-04-01 22:00:00", tz_offset=0):
        schedule.invoke({"draft_id": did})
    d = repo.get_draft(did)
    assert d is not None
    assert d.scheduled_for is not None
    # naive datetime stored; expect next day 19:00 local
    assert d.scheduled_for.day == 2


def test_publish_due_drafts_publishes_scheduled_past(repo: Repository, tmp_path: Path) -> None:
    img = tmp_path / "card.png"
    img.write_bytes(b"PNG")
    did = repo.create_draft(
        activity_id=1, platform=Platform.FACEBOOK, language=Language.PT,
        caption="x", media_paths=str(img),
    )
    repo.set_approved(did, post_now=False)
    repo.schedule_draft(did, dt.datetime(2026, 4, 1, 18, 0))

    fb = MagicMock()
    fb.publish.return_value = "fb-post-1"
    publishers = {Platform.FACEBOOK: fb, Platform.INSTAGRAM: MagicMock()}
    tools = build_publish_tools(
        repo=repo, publishers=publishers,
        publish_time_local="19:00", publish_timezone="Europe/Lisbon",
    )
    publish_due = next(t for t in tools if t.name == "publish_due_drafts")
    with freeze_time("2026-04-01 19:30:00"):
        result = publish_due.invoke({})
    assert "fb-post-1" in result
    fb.publish.assert_called_once()
    d = repo.get_draft(did)
    assert d is not None
    assert d.status == DraftStatus.PUBLISHED


def test_publish_due_drafts_publishes_post_now(repo: Repository, tmp_path: Path) -> None:
    img = tmp_path / "card.png"
    img.write_bytes(b"PNG")
    did = repo.create_draft(
        activity_id=1, platform=Platform.INSTAGRAM, language=Language.PT,
        caption="x", media_paths=str(img),
    )
    repo.set_approved(did, post_now=True)

    ig = MagicMock()
    ig.publish.return_value = "ig-post-1"
    publishers = {Platform.FACEBOOK: MagicMock(), Platform.INSTAGRAM: ig}
    tools = build_publish_tools(
        repo=repo, publishers=publishers,
        publish_time_local="19:00", publish_timezone="Europe/Lisbon",
    )
    publish_due = next(t for t in tools if t.name == "publish_due_drafts")
    publish_due.invoke({})
    ig.publish.assert_called_once()


def test_publish_to_facebook_refuses_unless_approved(repo: Repository) -> None:
    did = repo.create_draft(
        activity_id=1, platform=Platform.FACEBOOK, language=Language.PT, caption="x",
    )
    publishers = {Platform.FACEBOOK: MagicMock(), Platform.INSTAGRAM: MagicMock()}
    tools = build_publish_tools(
        repo=repo, publishers=publishers,
        publish_time_local="19:00", publish_timezone="Europe/Lisbon",
    )
    publish_fb = next(t for t in tools if t.name == "publish_to_facebook")
    result = publish_fb.invoke({"draft_id": did})
    assert "REJECTED" in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/agent/tools/test_publish_tools.py -v
```

Expected: import error.

- [ ] **Step 3: Implement publish tools**

```python
# src/cycling_agent/agent/tools/publish_tools.py
"""Publish-related tools.

- ``schedule_publish``: move an approved draft to ``scheduled`` with a scheduled_for
  time computed from PUBLISH_TIME_LOCAL / PUBLISH_TIMEZONE.
- ``publish_due_drafts``: publish anything ready (scheduled past due, or approved
  with post_now=True). The agent calls this once per cycle.
- ``publish_to_facebook`` / ``publish_to_instagram``: low-level direct publishers,
  guarded by status checks. The orchestrator usually does NOT call these directly;
  ``publish_due_drafts`` is the normal path.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

from langchain_core.tools import BaseTool, tool

from cycling_agent.db.models import DraftStatus, Platform
from cycling_agent.db.repo import Repository
from cycling_agent.publishers.base import Publisher, PublishRequest


def build_publish_tools(
    *,
    repo: Repository,
    publishers: dict[Platform, Publisher],
    publish_time_local: str,
    publish_timezone: str,
) -> list[BaseTool]:
    tz = ZoneInfo(publish_timezone)
    hh, mm = (int(x) for x in publish_time_local.split(":"))

    def _next_publish_window(now: dt.datetime) -> dt.datetime:
        local_now = now.astimezone(tz)
        candidate = local_now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if candidate <= local_now:
            candidate = candidate + dt.timedelta(days=1)
        return candidate.astimezone(dt.UTC).replace(tzinfo=None)

    def _publish(draft_id: int) -> str:
        d = repo.get_draft(draft_id)
        if d is None:
            return f"REJECTED: draft {draft_id} not found"
        if d.status not in (DraftStatus.SCHEDULED, DraftStatus.APPROVED):
            return f"REJECTED: draft {draft_id} status is {d.status.value}, not approved/scheduled"
        if d.status == DraftStatus.APPROVED and not d.post_now:
            return f"REJECTED: draft {draft_id} approved but not marked post_now; use schedule_publish"

        publisher = publishers[d.platform]
        request = PublishRequest(
            caption=(d.caption + ("\n" + d.hashtags if d.hashtags else "")).strip(),
            media_paths=[Path(p) for p in (d.media_paths or "").split(",") if p],
        )
        external_id = publisher.publish(request)
        repo.record_post(draft_id=draft_id, platform=d.platform, external_post_id=external_id)
        return external_id

    @tool
    def schedule_publish(draft_id: int) -> str:
        """Move an approved draft to scheduled state with the next publish window."""
        d = repo.get_draft(draft_id)
        if d is None:
            return f"REJECTED: draft {draft_id} not found"
        if d.status != DraftStatus.APPROVED:
            return f"REJECTED: draft {draft_id} status is {d.status.value}, not approved"
        if d.post_now:
            return f"REJECTED: draft {draft_id} is post_now; do not schedule, call publish_due_drafts instead"
        scheduled_for = _next_publish_window(dt.datetime.now(dt.UTC))
        repo.schedule_draft(draft_id, scheduled_for)
        return f"Draft {draft_id} scheduled for {scheduled_for.isoformat()}Z"

    @tool
    def publish_due_drafts() -> str:
        """Publish any draft that is scheduled past due, or approved with post_now."""
        due = repo.find_due_drafts(now=dt.datetime.now(dt.UTC))
        if not due:
            return "No drafts due."
        published_ids: list[str] = []
        for d in due:
            try:
                external = _publish(d.id)
                published_ids.append(f"{d.platform.value}:{external}")
            except Exception as e:
                published_ids.append(f"{d.platform.value}:ERROR:{e}")
        return "Published: " + ", ".join(published_ids)

    @tool
    def publish_to_facebook(draft_id: int) -> str:
        """Publish a single Facebook draft directly. Prefer publish_due_drafts."""
        return _publish(draft_id)

    @tool
    def publish_to_instagram(draft_id: int) -> str:
        """Publish a single Instagram draft directly. Prefer publish_due_drafts."""
        return _publish(draft_id)

    return [schedule_publish, publish_due_drafts, publish_to_facebook, publish_to_instagram]
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/agent/tools/test_publish_tools.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Lint + type check**

```bash
uv run ruff check src tests
uv run ty check src tests
```

- [ ] **Step 6: Commit**

```bash
git add src/cycling_agent/agent/tools/publish_tools.py tests/unit/agent/tools/test_publish_tools.py
git commit -m "feat(tools): add schedule_publish, publish_due_drafts, publish_to_*"
```

---

### Task 17: State tools (mark_processed, log_feedback)

**Files:**
- Create: `src/cycling_agent/agent/tools/state_tools.py`
- Create: `tests/unit/agent/tools/test_state_tools.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/agent/tools/test_state_tools.py
"""Tests for state-management tools."""

from __future__ import annotations

import datetime as dt

import pytest

from cycling_agent.agent.tools.state_tools import build_state_tools
from cycling_agent.db.engine import build_engine, build_session_factory, init_schema
from cycling_agent.db.models import ActivityStatus, DraftStatus, Language, Platform
from cycling_agent.db.repo import Repository


@pytest.fixture()
def repo() -> Repository:
    engine = build_engine(":memory:")
    init_schema(engine)
    repo = Repository(build_session_factory(engine))
    repo.upsert_activity(id=1, started_at=dt.datetime(2026, 4, 1), name="Crit", workout_type=11)
    return repo


def test_mark_processed_rejects_when_drafts_not_terminal(repo: Repository) -> None:
    repo.create_draft(activity_id=1, platform=Platform.FACEBOOK, language=Language.PT, caption="x")
    tools = build_state_tools(repo=repo)
    mark = next(t for t in tools if t.name == "mark_processed")
    result = mark.invoke({"activity_id": 1})
    assert "REJECTED" in result


def test_mark_processed_succeeds_when_all_terminal(repo: Repository) -> None:
    d1 = repo.create_draft(activity_id=1, platform=Platform.FACEBOOK, language=Language.PT, caption="x")
    d2 = repo.create_draft(activity_id=1, platform=Platform.INSTAGRAM, language=Language.PT, caption="y")
    repo.set_draft_status(d1, DraftStatus.PUBLISHED)
    repo.set_draft_status(d2, DraftStatus.REJECTED)
    tools = build_state_tools(repo=repo)
    mark = next(t for t in tools if t.name == "mark_processed")
    result = mark.invoke({"activity_id": 1})
    assert "processed" in result.lower()
    a = repo.get_activity(1)
    assert a is not None
    assert a.status == ActivityStatus.PROCESSED


def test_log_feedback_writes_event(repo: Repository) -> None:
    did = repo.create_draft(activity_id=1, platform=Platform.FACEBOOK, language=Language.PT, caption="x")
    tools = build_state_tools(repo=repo)
    log_fb = next(t for t in tools if t.name == "log_feedback")
    log_fb.invoke({"draft_id": did, "kind": "agent_note", "payload": "{\"observation\":\"caption was rewritten 3 times\"}"})
    events = repo.list_approval_events_for_draft(did)
    assert len(events) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/agent/tools/test_state_tools.py -v
```

Expected: import error.

- [ ] **Step 3: Implement state tools**

```python
# src/cycling_agent/agent/tools/state_tools.py
"""State-management tools."""

from __future__ import annotations

from langchain_core.tools import BaseTool, tool

from cycling_agent.db.repo import Repository


def build_state_tools(*, repo: Repository) -> list[BaseTool]:
    @tool
    def mark_processed(activity_id: int) -> str:
        """Mark an activity processed once all of its drafts are in a terminal state."""
        try:
            repo.mark_processed(activity_id)
        except ValueError as e:
            return f"REJECTED: {e}"
        return f"Activity {activity_id} marked processed."

    @tool
    def log_feedback(draft_id: int, kind: str, payload: str) -> str:
        """Append a free-form feedback event to the audit trail for a draft."""
        repo.log_approval_event(draft_id=draft_id, event=kind, payload=payload)
        return "ok"

    return [mark_processed, log_feedback]
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/agent/tools/test_state_tools.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Lint + type check**

```bash
uv run ruff check src tests
uv run ty check src tests
```

- [ ] **Step 6: Commit**

```bash
git add src/cycling_agent/agent/tools/state_tools.py tests/unit/agent/tools/test_state_tools.py
git commit -m "feat(tools): add mark_processed and log_feedback"
```

---


## Phase 5 — Sub-agents and orchestrator

### Task 18: Drafter sub-agent

**Files:**
- Create: `src/cycling_agent/agent/subagents/__init__.py`
- Create: `src/cycling_agent/agent/subagents/drafter.py`
- Create: `src/cycling_agent/agent/prompts/__init__.py`
- Create: `src/cycling_agent/agent/prompts/drafter.md`
- Create: `tests/unit/agent/subagents/__init__.py`
- Create: `tests/unit/agent/subagents/test_drafter.py`

The drafter is a deepagents sub-agent invoked by the orchestrator via the built-in `task` tool. It receives a single instruction string, drafts a caption, self-critiques, refines, and returns the final caption + hashtags. It does not need its own tools — the orchestrator passes everything in the prompt string.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/agent/subagents/test_drafter.py
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/agent/subagents/test_drafter.py -v
```

Expected: import error.

- [ ] **Step 3: Implement drafter prompt and definition**

```markdown
<!-- src/cycling_agent/agent/prompts/drafter.md -->
You are the **drafter**: write a single social-media caption for one platform and one language.

You will be given, in the user message:
- The platform (`facebook` or `instagram`).
- The language (`pt` or `en`).
- The activity summary (race name, distance, time, elevation, power, HR).
- The rider's "feeling" note (may be empty — handle gracefully).
- The sponsor list — every sponsor MUST appear in the final caption either by handle or by hashtag.
- 3–10 style examples — your output's voice MUST match these.
- Optional regenerate hint from the rider — apply it (e.g., "more grateful, less hype").

Process:

1. **Draft** a caption that fits the platform's norms:
   - Facebook: longer narrative (3–6 sentences), conversational, less hashtag-heavy.
   - Instagram: punchier (1–3 sentences), strong opening, more hashtags appropriate.
2. **Self-critique** against this checklist (write the critique inline as part of your reasoning):
   - Voice: does it sound like the style examples?
   - Sponsors: are ALL sponsor handles or hashtags present?
   - Length: appropriate for the platform?
   - Banned phrases: no "left it all on the road", "dug deep", "no pain no gain", or other clichés.
   - Feeling: if the rider provided a feeling note, does the caption reflect it?
3. **Refine** based on the critique. Repeat once if needed. Stop after at most two refinements.
4. **Return** the final caption and a separate line of hashtags. Use this exact format:

```
CAPTION:
<final caption text, no leading bullet>

HASHTAGS:
<space-separated hashtags including all sponsor hashtags>
```

Do not include any other text in your final answer. Do not write meta-commentary about the process in the final output.

Important constraints:
- Write in the requested language only. Do not mix languages.
- Never invent sponsors not listed.
- If the activity summary is missing power data, do not fabricate numbers — focus on the narrative instead.
```

```python
# src/cycling_agent/agent/subagents/__init__.py
"""Sub-agents for the orchestrator."""
```

```python
# src/cycling_agent/agent/prompts/__init__.py
"""Prompt loader utilities."""

from __future__ import annotations

from pathlib import Path

PROMPT_DIR = Path(__file__).resolve().parent


def load_prompt(name: str) -> str:
    return (PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8")
```

```python
# src/cycling_agent/agent/subagents/drafter.py
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
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/agent/subagents/test_drafter.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Lint + type check**

```bash
uv run ruff check src tests
uv run ty check src tests
```

- [ ] **Step 6: Commit**

```bash
git add src/cycling_agent/agent/subagents src/cycling_agent/agent/prompts \
        tests/unit/agent/subagents
git commit -m "feat(agent): add drafter sub-agent definition + prompt"
```

---

### Task 19: Reflector sub-agent

**Files:**
- Create: `src/cycling_agent/agent/subagents/reflector.py`
- Create: `src/cycling_agent/agent/prompts/reflector.md`
- Create: `tests/unit/agent/subagents/test_reflector.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/agent/subagents/test_reflector.py
"""Tests for the reflector sub-agent definition."""

from __future__ import annotations

from cycling_agent.agent.subagents.reflector import REFLECTOR_NAME, build_reflector_subagent


def test_reflector_definition_has_required_keys() -> None:
    sub = build_reflector_subagent()
    assert sub["name"] == REFLECTOR_NAME
    assert "reflect" in sub["description"].lower() or "feedback" in sub["description"].lower()
    assert "prompt" in sub


def test_reflector_prompt_mentions_diff_output() -> None:
    sub = build_reflector_subagent()
    p = sub["prompt"]
    assert "ADD" in p or "add" in p
    assert "REMOVE" in p or "remove" in p
    assert "diff" in p.lower() or "proposal" in p.lower()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/agent/subagents/test_reflector.py -v
```

Expected: import error.

- [ ] **Step 3: Implement reflector**

```markdown
<!-- src/cycling_agent/agent/prompts/reflector.md -->
You are the **reflector**: analyse the rider's recent approval feedback and propose improvements to the style guide.

You will receive in the user message:
- A list of `approval_events` from recent drafts: edits the rider made, regenerate hints, rejections, with the original caption and (where applicable) the rider's replacement.
- The current style examples for both languages.

Output a markdown document with three sections:

```
## ADD style examples

- (language) <quoted block of an actual edited caption that the rider produced and seems to embody desirable voice>
- ...

## REMOVE / RETIRE style examples

- (language) <reference to an existing example that contradicts recurring rider hints>
- ...

## STYLE GUIDE refinements

- <one-line rule extracted from recurring patterns, e.g., "Prefer past-tense recap over present-tense narration">
- ...
```

Rules:
- Only suggest additions when an edit indicates a clear stylistic preference. Do not promote a one-off rewrite.
- Only suggest removals when at least 2 regenerate hints contradict an example.
- Be conservative. It is better to propose nothing than to propose noise.
- Do NOT modify any files yourself. The rider applies the diff manually.

Length: keep the document under 400 words.
```

```python
# src/cycling_agent/agent/subagents/reflector.py
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
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/agent/subagents -v
```

Expected: all tests pass.

- [ ] **Step 5: Lint + type check**

```bash
uv run ruff check src tests
uv run ty check src tests
```

- [ ] **Step 6: Commit**

```bash
git add src/cycling_agent/agent/subagents/reflector.py \
        src/cycling_agent/agent/prompts/reflector.md \
        tests/unit/agent/subagents/test_reflector.py
git commit -m "feat(agent): add reflector sub-agent definition + prompt"
```

---

### Task 20: Orchestrator agent (deep agent + system prompt)

**Files:**
- Create: `src/cycling_agent/agent/orchestrator.py`
- Create: `src/cycling_agent/agent/prompts/orchestrator.md`
- Create: `tests/unit/agent/test_orchestrator.py`

- [ ] **Step 1: Write the orchestrator prompt**

```markdown
<!-- src/cycling_agent/agent/prompts/orchestrator.md -->
You are the **orchestrator** of the cycling-social-agent. You run once per scheduler tick and process new race activities.

# Standing instruction

Each invocation, follow this plan:

1. **list_new_races** — get the ids of races that need work.
2. For **at most one race** per invocation (the oldest first):
   1. Call **get_activity_detail** to fetch full data and persist the rider's "feeling" note.
   2. For each `(platform, language)` combination in `[(facebook, pt), (facebook, en), (instagram, pt), (instagram, en)]` that does not yet have a draft in `awaiting_approval`, `approved`, `scheduled`, `published`, or `rejected`:
      - Call **render_stats_card** and **render_route_map** to produce media (the route map may fail if the polyline is missing — proceed without it).
      - Read **read_sponsors** and **read_style_examples(language)**.
      - Spawn the **drafter** sub-agent with all of: platform, language, activity summary text (use the output of `get_activity_detail`), feeling text (from `get_feeling`), sponsor list, style examples, and any regenerate hint (from `check_approval_status` if applicable).
      - Parse the drafter's output (CAPTION: ... HASHTAGS: ...).
      - Call **send_for_approval** with the parsed caption + hashtags + media paths.
3. For each draft already in `awaiting_approval`, call **check_approval_status**:
   - If `approved post_now=false` → **schedule_publish**.
   - If `approved post_now=true` → it will be picked up by `publish_due_drafts` in step 4.
   - If `regenerate hint=...` → spawn the drafter sub-agent again with the hint, then `send_for_approval` with the new caption.
   - If `editing` → the rider is composing a replacement; do nothing this cycle.
   - If `rejected` → no action.
4. Call **publish_due_drafts** once per cycle.
5. For each activity whose drafts are all in terminal states (`published` or `rejected`), call **mark_processed**.
6. Stop. Do NOT loop. Do NOT process more than one race per invocation.

# Hard rules

- You MAY NOT publish without an approval. The publish tools enforce this; do not try to bypass.
- You MAY NOT silently skip a sponsor. The `send_for_approval` tool refuses if a sponsor is missing — re-spawn the drafter with an explicit reminder if that happens. Cap retries at 3.
- You MAY NOT read or write files outside the tools provided.
- If a tool returns "REJECTED: ...", read the message and act accordingly (re-draft, retry, or surface to the rider via `log_feedback`).

# Output

Return a short summary of what you did this cycle (1–3 sentences). The summary is logged for observability.
```

- [ ] **Step 2: Write the failing test**

```python
# tests/unit/agent/test_orchestrator.py
"""Tests for orchestrator construction.

We do not invoke the LLM in unit tests — that's covered in the smoke test (T26).
Here we only assert the orchestrator is built with the expected tools and sub-agents.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cycling_agent.agent.orchestrator import OrchestratorDeps, build_orchestrator
from cycling_agent.db.engine import build_engine, build_session_factory, init_schema
from cycling_agent.db.models import Platform
from cycling_agent.db.repo import Repository


@pytest.fixture()
def deps(tmp_path: Path) -> OrchestratorDeps:
    engine = build_engine(":memory:")
    init_schema(engine)
    repo = Repository(build_session_factory(engine))
    return OrchestratorDeps(
        repo=repo,
        strava_client=MagicMock(),
        strava_poller=MagicMock(),
        publishers={Platform.FACEBOOK: MagicMock(), Platform.INSTAGRAM: MagicMock()},
        approval_bot=MagicMock(),
        media_dir=tmp_path / "media",
        publish_time_local="19:00",
        publish_timezone="Europe/Lisbon",
        orchestrator_model="claude-haiku-4-5-20251001",
        drafter_model="claude-sonnet-4-6",
    )


def test_collect_tools_returns_expected_names(deps: OrchestratorDeps) -> None:
    from cycling_agent.agent.orchestrator import _collect_tools

    tools = _collect_tools(deps)
    names = {t.name for t in tools}
    assert {
        "list_new_races", "get_activity_detail", "get_feeling",
        "read_sponsors", "read_style_examples",
        "render_stats_card", "render_route_map",
        "send_for_approval", "check_approval_status",
        "schedule_publish", "publish_due_drafts",
        "publish_to_facebook", "publish_to_instagram",
        "mark_processed", "log_feedback",
    }.issubset(names)


def test_build_orchestrator_returns_agent(deps: OrchestratorDeps, monkeypatch: pytest.MonkeyPatch) -> None:
    # Stub deepagents.create_deep_agent so the test does not require a live API key.
    captured: dict = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return MagicMock(name="fake-agent")

    monkeypatch.setattr("cycling_agent.agent.orchestrator.create_deep_agent", fake_create)
    agent = build_orchestrator(deps)

    assert agent is not None
    assert "tools" in captured
    assert "instructions" in captured
    assert "subagents" in captured
    sub_names = {s["name"] for s in captured["subagents"]}
    assert {"drafter", "reflector"}.issubset(sub_names)
```

- [ ] **Step 3: Run test to verify it fails**

```bash
uv run pytest tests/unit/agent/test_orchestrator.py -v
```

Expected: import error.

- [ ] **Step 4: Implement the orchestrator**

```python
# src/cycling_agent/agent/orchestrator.py
"""Build the deep-agent orchestrator with all tools and sub-agents wired in."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from langchain_anthropic import ChatAnthropic

from cycling_agent.agent.prompts import load_prompt
from cycling_agent.agent.subagents.drafter import build_drafter_subagent
from cycling_agent.agent.subagents.reflector import build_reflector_subagent
from cycling_agent.agent.tools.approval_tools import build_approval_tools
from cycling_agent.agent.tools.content_tools import build_content_tools
from cycling_agent.agent.tools.media_tools import build_media_tools
from cycling_agent.agent.tools.publish_tools import build_publish_tools
from cycling_agent.agent.tools.state_tools import build_state_tools
from cycling_agent.agent.tools.strava_tools import build_strava_tools
from cycling_agent.approval.bot import ApprovalBot
from cycling_agent.db.models import Platform
from cycling_agent.db.repo import Repository
from cycling_agent.publishers.base import Publisher
from cycling_agent.strava.client import StravaClient
from cycling_agent.strava.poller import StravaPoller


@dataclasses.dataclass
class OrchestratorDeps:
    repo: Repository
    strava_client: StravaClient
    strava_poller: StravaPoller
    publishers: dict[Platform, Publisher]
    approval_bot: ApprovalBot
    media_dir: Path
    publish_time_local: str
    publish_timezone: str
    orchestrator_model: str
    drafter_model: str


def _collect_tools(deps: OrchestratorDeps) -> list[Any]:
    tools: list[Any] = []
    tools.extend(build_strava_tools(repo=deps.repo, client=deps.strava_client, poller=deps.strava_poller))
    tools.extend(build_content_tools(repo=deps.repo))
    tools.extend(build_media_tools(repo=deps.repo, strava=deps.strava_client, media_dir=deps.media_dir))
    tools.extend(build_approval_tools(repo=deps.repo, bot=deps.approval_bot))
    tools.extend(
        build_publish_tools(
            repo=deps.repo,
            publishers=deps.publishers,
            publish_time_local=deps.publish_time_local,
            publish_timezone=deps.publish_timezone,
        )
    )
    tools.extend(build_state_tools(repo=deps.repo))
    return tools


def build_orchestrator(deps: OrchestratorDeps) -> Any:
    """Build the deep-agent orchestrator. Returns the runnable agent."""
    tools = _collect_tools(deps)
    instructions = load_prompt("orchestrator")
    subagents = [build_drafter_subagent(), build_reflector_subagent()]
    model = ChatAnthropic(model=deps.orchestrator_model, max_tokens=4096)

    return create_deep_agent(
        tools=tools,
        instructions=instructions,
        subagents=subagents,
        model=model,
    )
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/unit/agent/test_orchestrator.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Lint + type check**

```bash
uv run ruff check src tests
uv run ty check src tests
```

- [ ] **Step 7: Commit**

```bash
git add src/cycling_agent/agent/orchestrator.py src/cycling_agent/agent/prompts/orchestrator.md \
        tests/unit/agent/test_orchestrator.py
git commit -m "feat(agent): wire deep-agent orchestrator with all tools and subagents"
```

---

### Task 21: Runner (scheduler loop)

**Files:**
- Create: `src/cycling_agent/agent/runner.py`
- Create: `tests/unit/agent/test_runner.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/agent/test_runner.py
"""Tests for the agent runner (scheduler-driven invocation)."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from cycling_agent.agent.runner import AgentRunner
from cycling_agent.db.engine import build_engine, build_session_factory, init_schema
from cycling_agent.db.repo import Repository


@pytest.fixture()
def repo() -> Repository:
    engine = build_engine(":memory:")
    init_schema(engine)
    return Repository(build_session_factory(engine))


async def test_run_once_invokes_orchestrator(repo: Repository) -> None:
    fake_agent = MagicMock()
    fake_agent.invoke.return_value = {"messages": [MagicMock(content="processed activity 1")]}
    runner = AgentRunner(orchestrator=fake_agent, repo=repo)
    outcome = await runner.run_once()
    assert "processed" in outcome.lower()
    fake_agent.invoke.assert_called_once()


async def test_run_once_records_agent_run(repo: Repository) -> None:
    fake_agent = MagicMock()
    fake_agent.invoke.return_value = {"messages": [MagicMock(content="ok")]}
    runner = AgentRunner(orchestrator=fake_agent, repo=repo)
    await runner.run_once()

    from sqlalchemy import select

    from cycling_agent.db.models import AgentRun

    with repo._session_factory() as s:  # noqa: SLF001 - test introspection
        runs = list(s.execute(select(AgentRun)).scalars().all())
        assert len(runs) == 1
        assert runs[0].outcome == "ok"


async def test_run_once_records_failure(repo: Repository) -> None:
    fake_agent = MagicMock()
    fake_agent.invoke.side_effect = RuntimeError("boom")
    runner = AgentRunner(orchestrator=fake_agent, repo=repo)
    outcome = await runner.run_once()
    assert "error" in outcome.lower()

    with repo._session_factory() as s:  # noqa: SLF001
        from sqlalchemy import select
        from cycling_agent.db.models import AgentRun
        runs = list(s.execute(select(AgentRun)).scalars().all())
        assert runs[-1].outcome == "error"
        assert "boom" in (runs[-1].error_text or "")


async def test_run_forever_stops_on_event(repo: Repository) -> None:
    fake_agent = MagicMock()
    fake_agent.invoke.return_value = {"messages": [MagicMock(content="ok")]}
    runner = AgentRunner(orchestrator=fake_agent, repo=repo, interval_seconds=0.01)

    stop = asyncio.Event()
    task = asyncio.create_task(runner.run_forever(stop_event=stop))
    await asyncio.sleep(0.05)
    stop.set()
    await task

    assert fake_agent.invoke.call_count >= 2


async def test_run_once_passes_recursion_limit(repo: Repository) -> None:
    fake_agent = MagicMock()
    fake_agent.invoke.return_value = {"messages": [MagicMock(content="ok")]}
    runner = AgentRunner(orchestrator=fake_agent, repo=repo, recursion_limit=42)
    await runner.run_once()
    config = fake_agent.invoke.call_args.kwargs.get("config", {})
    assert config.get("recursion_limit") == 42


async def test_consecutive_failures_trigger_bot_alert(repo: Repository) -> None:
    fake_agent = MagicMock()
    fake_agent.invoke.side_effect = RuntimeError("boom")

    fake_bot = MagicMock()

    async def _send_card(*args, **kwargs):
        return 1

    fake_bot.send_draft_card = AsyncMock(side_effect=_send_card)
    fake_bot._chat_id = 1
    fake_bot._bot = MagicMock()
    fake_bot._bot.send_message = AsyncMock()

    runner = AgentRunner(
        orchestrator=fake_agent, repo=repo,
        approval_bot=fake_bot, failure_alert_threshold=3,
    )
    for _ in range(3):
        await runner.run_once()
    fake_bot._bot.send_message.assert_awaited()
    text = fake_bot._bot.send_message.await_args.kwargs.get("text", "")
    assert "3" in text and "fail" in text.lower()


async def test_success_resets_failure_counter(repo: Repository) -> None:
    fake_agent = MagicMock()
    fake_agent.invoke.side_effect = [
        RuntimeError("boom"),
        RuntimeError("boom"),
        {"messages": [MagicMock(content="ok")]},
        RuntimeError("boom"),
    ]

    fake_bot = MagicMock()
    fake_bot._chat_id = 1
    fake_bot._bot = MagicMock()
    fake_bot._bot.send_message = AsyncMock()

    runner = AgentRunner(
        orchestrator=fake_agent, repo=repo,
        approval_bot=fake_bot, failure_alert_threshold=3,
    )
    for _ in range(4):
        await runner.run_once()

    # 2 failures, 1 success (counter resets), 1 failure → never hits threshold
    fake_bot._bot.send_message.assert_not_awaited()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/agent/test_runner.py -v
```

Expected: import error.

- [ ] **Step 3: Implement the runner**

```python
# src/cycling_agent/agent/runner.py
"""Agent runner: invokes the orchestrator on a fixed interval.

- Records each invocation as an ``AgentRun`` row for observability.
- Caps tool-call recursion via langgraph ``recursion_limit`` (spec §10).
- Tracks consecutive failures and alerts the rider via Telegram after a
  configurable threshold (spec §11).
- Designed to share an asyncio event loop with the Telegram bot.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from typing import Any, Optional

import structlog

from cycling_agent.db.models import AgentRun
from cycling_agent.db.repo import Repository

log = structlog.get_logger(__name__)


class AgentRunner:
    def __init__(
        self,
        *,
        orchestrator: Any,
        repo: Repository,
        interval_seconds: float = 600,
        recursion_limit: int = 30,
        approval_bot: Optional[Any] = None,
        failure_alert_threshold: int = 5,
    ) -> None:
        self._orchestrator = orchestrator
        self._repo = repo
        self._interval = interval_seconds
        self._recursion_limit = recursion_limit
        self._bot = approval_bot
        self._failure_threshold = failure_alert_threshold
        self._consecutive_failures = 0

    async def run_once(self) -> str:
        """Invoke the orchestrator one time and record the outcome."""
        run = AgentRun(started_at=dt.datetime.now(dt.UTC))
        with self._repo._session_factory() as s:  # noqa: SLF001 - intentional access
            s.add(run)
            s.commit()
            run_id = run.id

        try:
            # The orchestrator is sync (LangGraph compiled graph). Run in a thread
            # so it does not block the event loop (Telegram bot, etc).
            result = await asyncio.to_thread(
                self._orchestrator.invoke,
                {"messages": [{"role": "user", "content": "Process new race activities."}]},
                config={"recursion_limit": self._recursion_limit},
            )
            messages = result.get("messages", [])
            outcome_text = messages[-1].content if messages else "ok"
            outcome_summary = "ok"
            error_text: Optional[str] = None
            self._consecutive_failures = 0
            log.info("agent.run.complete", run_id=run_id, summary=outcome_text[:200])
        except Exception as e:  # noqa: BLE001 - we want to record any failure
            outcome_text = f"error: {e}"
            outcome_summary = "error"
            error_text = str(e)
            self._consecutive_failures += 1
            log.error("agent.run.failed", run_id=run_id, error=str(e), exc_info=True)
            if self._consecutive_failures >= self._failure_threshold:
                await self._maybe_alert(self._consecutive_failures, str(e))

        with self._repo._session_factory() as s:  # noqa: SLF001
            row = s.get(AgentRun, run_id)
            if row is not None:
                row.finished_at = dt.datetime.now(dt.UTC)
                row.outcome = outcome_summary
                row.error_text = error_text
                s.commit()

        return outcome_text

    async def run_forever(self, *, stop_event: asyncio.Event) -> None:
        """Run the orchestrator on a fixed interval until ``stop_event`` is set."""
        while not stop_event.is_set():
            await self.run_once()
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=self._interval)
            except TimeoutError:
                continue

    async def _maybe_alert(self, count: int, error: str) -> None:
        if self._bot is None or self._bot._bot is None or not self._bot._chat_id:  # noqa: SLF001
            return
        try:
            await self._bot._bot.send_message(  # noqa: SLF001
                chat_id=self._bot._chat_id,  # noqa: SLF001
                text=f"⚠️ cycling-agent: {count} consecutive failures. Last error: {error[:300]}",
            )
        except Exception as e:  # noqa: BLE001
            log.error("agent.alert.send_failed", error=str(e))
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/agent/test_runner.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Lint + type check**

```bash
uv run ruff check src tests
uv run ty check src tests
```

- [ ] **Step 6: Commit**

```bash
git add src/cycling_agent/agent/runner.py tests/unit/agent/test_runner.py
git commit -m "feat(agent): add interval-based AgentRunner with run-row observability"
```

---


## Phase 6 — Main entry, CLI, smoke test, docs

### Task 22: Main entry + `serve` CLI command

**Files:**
- Create: `src/cycling_agent/main.py`
- Modify: `src/cycling_agent/cli.py` (add `serve` subcommand)
- Create: `tests/unit/test_main.py`

The `serve` command wires everything together: builds repo + Strava client + publishers + bot + orchestrator + runner, registers Telegram handlers, starts both the bot polling loop and the agent runner loop, and waits for SIGINT/SIGTERM for clean shutdown.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_main.py
"""Tests for main entry wiring (no real network)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cycling_agent.config import Settings
from cycling_agent.main import build_publishers, build_strava


def test_build_strava_returns_configured_client() -> None:
    settings = Settings()
    settings.strava_client_id = "1"
    settings.strava_client_secret = "secret"
    settings.strava_refresh_token = "refresh"
    client = build_strava(settings)
    assert client is not None


def test_build_publishers_dry_run_returns_both(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings()
    settings.dry_run = True
    publishers = build_publishers(settings)
    from cycling_agent.db.models import Platform
    assert Platform.FACEBOOK in publishers
    assert Platform.INSTAGRAM in publishers
    # Dry-run publishers do not require any real API objects.
    from cycling_agent.publishers.facebook import FacebookPublisher
    from cycling_agent.publishers.instagram import InstagramPublisher
    assert isinstance(publishers[Platform.FACEBOOK], FacebookPublisher)
    assert isinstance(publishers[Platform.INSTAGRAM], InstagramPublisher)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_main.py -v
```

Expected: import error.

- [ ] **Step 3: Implement main entry**

```python
# src/cycling_agent/main.py
"""Application entry point.

``serve_async`` builds all components from ``Settings`` and runs the Telegram
bot + agent runner concurrently until SIGINT/SIGTERM. ``serve`` is the
sync click-friendly wrapper.
"""

from __future__ import annotations

import asyncio
import signal
from pathlib import Path

import structlog
from telegram.ext import Application

from cycling_agent.agent.orchestrator import OrchestratorDeps, build_orchestrator
from cycling_agent.agent.runner import AgentRunner
from cycling_agent.approval.bot import ApprovalBot
from cycling_agent.config import Settings, load_settings
from cycling_agent.db.engine import build_engine, build_session_factory, init_schema
from cycling_agent.db.models import Platform
from cycling_agent.db.repo import Repository
from cycling_agent.logging import configure_logging
from cycling_agent.publishers.base import Publisher
from cycling_agent.publishers.facebook import FacebookPublisher
from cycling_agent.publishers.instagram import InstagramPublisher
from cycling_agent.strava.client import StravaClient
from cycling_agent.strava.poller import StravaPoller

log = structlog.get_logger(__name__)


def build_repo(settings: Settings) -> Repository:
    engine = build_engine(settings.db_path)
    init_schema(engine)
    return Repository(build_session_factory(engine))


def build_strava(settings: Settings) -> StravaClient:
    return StravaClient(
        client_id=settings.strava_client_id or None,
        client_secret=settings.strava_client_secret or None,
        refresh_token=settings.strava_refresh_token or None,
    )


def build_publishers(settings: Settings) -> dict[Platform, Publisher]:
    """Build platform publishers. Real API objects are constructed lazily."""
    if settings.dry_run:
        return {
            Platform.FACEBOOK: FacebookPublisher(page=None, ig_business_id=None, dry_run=True),
            Platform.INSTAGRAM: InstagramPublisher(page=None, ig=None, dry_run=True),
        }

    from facebook_business.adobjects.iguser import IGUser
    from facebook_business.adobjects.page import Page
    from facebook_business.api import FacebookAdsApi

    FacebookAdsApi.init(
        app_id=settings.meta_app_id,
        app_secret=settings.meta_app_secret,
        access_token=settings.meta_page_access_token,
    )
    page = Page(settings.meta_page_id)
    ig = IGUser(settings.meta_ig_business_id)

    return {
        Platform.FACEBOOK: FacebookPublisher(page=page, ig_business_id=settings.meta_ig_business_id, dry_run=False),
        Platform.INSTAGRAM: InstagramPublisher(page=page, ig=ig, dry_run=False),
    }


async def serve_async(settings: Settings) -> None:
    configure_logging(settings.log_level)
    log.info("startup", dry_run=settings.dry_run, db=settings.db_path)

    repo = build_repo(settings)
    strava = build_strava(settings)
    poller = StravaPoller(client=strava, repo=repo)
    publishers = build_publishers(settings)

    application = Application.builder().token(settings.telegram_bot_token).build()
    chat_id = int(settings.telegram_chat_id) if settings.telegram_chat_id else 0
    bot = ApprovalBot(repo=repo, chat_id=chat_id)
    bot.register_handlers(application)

    deps = OrchestratorDeps(
        repo=repo,
        strava_client=strava,
        strava_poller=poller,
        publishers=publishers,
        approval_bot=bot,
        media_dir=Path("data/media"),
        publish_time_local=settings.publish_time_local,
        publish_timezone=settings.publish_timezone,
        orchestrator_model=settings.orchestrator_model,
        drafter_model=settings.drafter_model,
    )
    orchestrator = build_orchestrator(deps)
    runner = AgentRunner(
        orchestrator=orchestrator,
        repo=repo,
        interval_seconds=settings.poll_interval_seconds,
        approval_bot=bot,
    )

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    log.info("telegram_bot.started")

    try:
        await runner.run_forever(stop_event=stop_event)
    finally:
        log.info("shutdown.begin")
        await application.updater.stop()
        await application.stop()
        await application.shutdown()
        log.info("shutdown.complete")


def serve() -> None:
    """Sync entry point used by the click ``serve`` command."""
    settings = load_settings()
    asyncio.run(serve_async(settings))
```

- [ ] **Step 4: Wire the `serve` command into the CLI**

Edit `src/cycling_agent/cli.py` and add the `serve` subcommand at the bottom (before `def main`):

```python
@cli.command("serve")
@click.option("--dry-run/--live", default=None, help="Override DRY_RUN env var")
def serve_cmd(dry_run: bool | None) -> None:
    """Run the agent + Telegram bot in the foreground."""
    from cycling_agent.main import serve_async

    settings = load_settings()
    if dry_run is not None:
        settings.dry_run = dry_run
    asyncio.run(serve_async(settings))
```

Add at the top of `cli.py`:
```python
import asyncio
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/unit/test_main.py -v
```

Expected: tests pass.

- [ ] **Step 6: Smoke-check the CLI loads (no real Telegram token, will fail to start)**

```bash
DRY_RUN=true TELEGRAM_BOT_TOKEN=fake TELEGRAM_CHAT_ID=1 ANTHROPIC_API_KEY=fake \
  uv run cycling-agent serve --help
```

Expected: usage text printed; no import error.

- [ ] **Step 7: Lint + type check**

```bash
uv run ruff check src tests
uv run ty check src tests
```

- [ ] **Step 8: Commit**

```bash
git add src/cycling_agent/main.py src/cycling_agent/cli.py tests/unit/test_main.py
git commit -m "feat: wire main entry that runs telegram bot + agent runner"
```

---

### Task 23: `reflect` CLI command

**Files:**
- Modify: `src/cycling_agent/cli.py`
- Create: `src/cycling_agent/agent/reflect.py`
- Create: `tests/unit/agent/test_reflect.py`

The reflect command runs the reflector sub-agent against recent approval events and writes the proposal to `data/reflect-proposals/YYYY-MM-DD.md`. The rider applies the diff manually.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/agent/test_reflect.py
"""Tests for the reflect command."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from unittest.mock import MagicMock, patch

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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/agent/test_reflect.py -v
```

Expected: import error.

- [ ] **Step 3: Implement reflect**

```python
# src/cycling_agent/agent/reflect.py
"""Run the reflector against recent approval events and write a proposal file."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

from cycling_agent.agent.prompts import load_prompt
from cycling_agent.db.models import Language
from cycling_agent.db.repo import Repository


def _build_user_message(repo: Repository, since: dt.datetime) -> str:
    events = repo.list_recent_approval_events(since=since)
    if not events:
        events_text = "(none)"
    else:
        lines = [
            f"- {e.at.isoformat()} draft={e.draft_id} event={e.event} payload={e.payload or '{}'}"
            for e in events
        ]
        events_text = "\n".join(lines)

    pt_examples = "\n\n---\n\n".join(ex.text for ex in repo.list_style_examples(Language.PT))
    en_examples = "\n\n---\n\n".join(ex.text for ex in repo.list_style_examples(Language.EN))

    return (
        f"# Recent approval events (since {since.isoformat()})\n\n{events_text}\n\n"
        f"# Current PT style examples\n\n{pt_examples or '(none)'}\n\n"
        f"# Current EN style examples\n\n{en_examples or '(none)'}\n"
    )


def run_reflect(
    *,
    repo: Repository,
    llm: Any,
    output_dir: Path,
    now: dt.datetime,
    lookback_days: int = 30,
) -> Path:
    """Generate a reflection proposal and write it to disk. Returns the path."""
    since = now - dt.timedelta(days=lookback_days)
    system = load_prompt("reflector")
    user = _build_user_message(repo, since)

    response = llm.invoke([{"role": "system", "content": system}, {"role": "user", "content": user}])
    body = getattr(response, "content", str(response))

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{now.date().isoformat()}.md"
    out_path.write_text(body, encoding="utf-8")
    return out_path
```

- [ ] **Step 4: Wire `reflect` into the CLI**

Append to `src/cycling_agent/cli.py`:

```python
@cli.command("reflect")
def reflect_cmd() -> None:
    """Generate a style-guide diff proposal from recent approval feedback."""
    from cycling_agent.agent.reflect import run_reflect
    from langchain_anthropic import ChatAnthropic
    import datetime as _dt

    settings = load_settings()
    repo = _build_repo()
    llm = ChatAnthropic(model=settings.reflector_model, max_tokens=2048)
    out_dir = Path("data/reflect-proposals")
    path = run_reflect(repo=repo, llm=llm, output_dir=out_dir, now=_dt.datetime.now(_dt.UTC))
    click.echo(f"wrote proposal: {path}")
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/unit/agent/test_reflect.py -v
```

Expected: tests pass.

- [ ] **Step 6: Lint + type check**

```bash
uv run ruff check src tests
uv run ty check src tests
```

- [ ] **Step 7: Commit**

```bash
git add src/cycling_agent/agent/reflect.py src/cycling_agent/cli.py \
        tests/unit/agent/test_reflect.py
git commit -m "feat(reflect): add reflect command that writes style-guide proposals"
```

---

### Task 24: End-to-end smoke test (dry-run, tools-in-order)

**Files:**
- Create: `tests/integration/__init__.py`
- Create: `tests/integration/test_dry_run_workflow.py`

This test exercises the full happy-path workflow without running the LLM orchestrator. It seeds a fixture race, calls each tool in the order the orchestrator would, simulates the rider tapping "Approve & post now", and asserts terminal state.

- [ ] **Step 1: Write the smoke test**

```python
# tests/integration/test_dry_run_workflow.py
"""End-to-end smoke test of the workflow with the LLM orchestrator stubbed out.

We exercise the tools directly in the order the orchestrator would, to verify
the tool layer integrates correctly. The drafter sub-agent is not invoked;
we feed a hand-written caption that satisfies the sponsor invariant.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from cycling_agent.agent.tools.approval_tools import build_approval_tools
from cycling_agent.agent.tools.content_tools import build_content_tools
from cycling_agent.agent.tools.media_tools import build_media_tools
from cycling_agent.agent.tools.publish_tools import build_publish_tools
from cycling_agent.agent.tools.state_tools import build_state_tools
from cycling_agent.agent.tools.strava_tools import build_strava_tools
from cycling_agent.db.engine import build_engine, build_session_factory, init_schema
from cycling_agent.db.models import ActivityStatus, Platform, Sponsor
from cycling_agent.db.repo import Repository
from cycling_agent.publishers.facebook import FacebookPublisher
from cycling_agent.publishers.instagram import InstagramPublisher
from cycling_agent.strava.client import StravaActivity


def _activity() -> StravaActivity:
    return StravaActivity(
        id=14738291734, name="Volta ao Algarve", workout_type=11,
        started_at=dt.datetime(2026, 2, 19, 13, 30, tzinfo=dt.UTC),
        distance_m=158420, moving_time_s=12640, elevation_gain_m=1834,
        avg_speed_mps=12.5, avg_power_w=268, norm_power_w=305,
        avg_hr=162, max_hr=188, kilojoules=3387,
        feeling_text="Etapa difícil, top 15.", polyline=None,
    )


def test_full_workflow_dry_run_publishes_and_marks_processed(tmp_path: Path) -> None:
    # --- setup -----------------------------------------------------------
    engine = build_engine(":memory:")
    init_schema(engine)
    repo = Repository(build_session_factory(engine))
    repo.replace_sponsors([
        Sponsor(name="BrandX", handle_facebook="@brandx", handle_instagram="@brandx", hashtag="#brandx"),
    ])

    fake_strava = MagicMock()
    fake_strava.get_activity_detail.return_value = _activity()
    fake_poller = MagicMock()
    fake_poller.poll.return_value = [14738291734]
    repo.upsert_activity(
        id=14738291734, started_at=dt.datetime(2026, 2, 19, 13, 30),
        name="Volta", workout_type=11,
    )

    fake_bot = MagicMock()
    fake_bot.send_draft_card = AsyncMock(return_value=4242)

    publishers = {
        Platform.FACEBOOK: FacebookPublisher(page=None, ig_business_id=None, dry_run=True),
        Platform.INSTAGRAM: InstagramPublisher(page=None, ig=None, dry_run=True),
    }

    media_dir = tmp_path / "media"
    strava_tools = build_strava_tools(repo=repo, client=fake_strava, poller=fake_poller)
    content_tools = build_content_tools(repo=repo)
    media_tools = build_media_tools(repo=repo, strava=fake_strava, media_dir=media_dir)
    approval_tools = build_approval_tools(repo=repo, bot=fake_bot)
    publish_tools = build_publish_tools(
        repo=repo, publishers=publishers,
        publish_time_local="19:00", publish_timezone="Europe/Lisbon",
    )
    state_tools = build_state_tools(repo=repo)

    def by_name(tools, name):
        return next(t for t in tools if t.name == name)

    # --- step 1: list new races --------------------------------------------
    out = by_name(strava_tools, "list_new_races").invoke({})
    assert "14738291734" in out

    # --- step 2: get_activity_detail ---------------------------------------
    by_name(strava_tools, "get_activity_detail").invoke({"activity_id": 14738291734})

    # --- step 3: render stats card (no map: polyline is None) --------------
    stats_path = by_name(media_tools, "render_stats_card").invoke({"activity_id": 14738291734})
    assert Path(stats_path).exists()

    # --- step 4: send_for_approval (FB/PT) ---------------------------------
    caption = "Etapa difícil mas valeu. Obrigado @brandx pelo apoio. #brandx"
    result = by_name(approval_tools, "send_for_approval").invoke({
        "activity_id": 14738291734, "platform": "facebook", "language": "pt",
        "caption": caption, "hashtags": "", "media_paths": stats_path,
    })
    assert "Sent" in result

    # --- step 5: simulate rider tapping "Approve & post now" --------------
    drafts = repo.list_drafts_in_states([__import__("cycling_agent.db.models", fromlist=["DraftStatus"]).DraftStatus.AWAITING_APPROVAL])
    assert len(drafts) == 1
    draft_id = drafts[0].id
    repo.set_approved(draft_id, post_now=True)

    # --- step 6: publish_due_drafts ----------------------------------------
    published = by_name(publish_tools, "publish_due_drafts").invoke({})
    assert "facebook:dry-run-fb-" in published

    # --- step 7: mark_processed --------------------------------------------
    # The activity has only one draft and it is now in PUBLISHED state.
    out = by_name(state_tools, "mark_processed").invoke({"activity_id": 14738291734})
    assert "processed" in out.lower()

    a = repo.get_activity(14738291734)
    assert a is not None
    assert a.status == ActivityStatus.PROCESSED
```

- [ ] **Step 2: Run the smoke test**

```bash
uv run pytest tests/integration/test_dry_run_workflow.py -v
```

Expected: passes.

- [ ] **Step 3: Run the full test suite + coverage**

```bash
uv run pytest -v
```

Expected: all tests pass; coverage report printed.

- [ ] **Step 4: Lint + type check**

```bash
uv run ruff check src tests
uv run ty check src tests
```

- [ ] **Step 5: Commit**

```bash
git add tests/integration
git commit -m "test(integration): add dry-run end-to-end smoke test"
```

---

### Task 25: README and setup docs

**Files:**
- Modify: `README.md`
- Create: `docs/setup.md`

- [ ] **Step 1: Write the README**

```markdown
# cycling-social-agent

Personal automation agent that turns Strava race activities into approval-gated social posts on Facebook and Instagram.

## What it does

1. Polls Strava every 10 minutes (configurable) for activities with `workout_type=Race`.
2. For each new race, generates four drafts: Facebook + Instagram, in Portuguese + English. Drafts use a per-race "feeling" note (the activity's private description in Strava) and few-shot voice examples from past posts.
3. Sends each draft to your Telegram with inline buttons: Approve (queued), Approve & post now, Edit, Regenerate, Reject, Reschedule.
4. Approved drafts are queued for `PUBLISH_TIME_LOCAL` (default 19:00 Lisbon time). "Approve & post now" publishes immediately.
5. All four drafts must include every sponsor — the agent enforces this as a hard invariant.

See the [design spec](docs/superpowers/specs/2026-04-15-cycling-social-agent-design.md) for the full architecture.

## Setup

See [docs/setup.md](docs/setup.md).

## Daily use

```bash
# foreground (use a terminal multiplexer):
uv run cycling-agent serve

# in dry-run (no real posts published):
uv run cycling-agent serve --dry-run

# Tell me what to improve in my style examples based on recent edits:
uv run cycling-agent reflect

# Reload sponsors after editing data/sponsors.yaml:
uv run cycling-agent seed-sponsors

# Reload style examples after editing the markdown files:
uv run cycling-agent seed-style --lang pt --path data/style_examples_pt.md
uv run cycling-agent seed-style --lang en --path data/style_examples_en.md
```

## Development

```bash
make test       # not provided by default; run uv run pytest -q instead
uv run pytest -q
uv run ruff check --fix src tests
uv run ruff format src tests
uv run ty check src tests
```

## License

Personal use. No license granted.
```

- [ ] **Step 2: Write `docs/setup.md`**

```markdown
# Setup

## 1. Install

Install `uv` (https://docs.astral.sh/uv/) then:

```bash
git clone <this repo>
cd cycling-social-agent
uv sync
```

## 2. Strava

1. Create an API application at https://www.strava.com/settings/api. Note your `Client ID` and `Client Secret`.
2. Use the [strava-tokens helper](https://developers.strava.com/docs/getting-started/) (or any OAuth flow) to exchange your authorisation code for a refresh token.
3. Confirm with `curl -X POST https://www.strava.com/api/v3/oauth/token -F client_id=... -F client_secret=... -F grant_type=refresh_token -F refresh_token=...` that you can refresh.

Put `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`, `STRAVA_REFRESH_TOKEN`, and `STRAVA_ATHLETE_ID` in `.env`.

## 3. Meta (Facebook + Instagram)

1. Convert the Instagram account to **Business** or **Creator** and link it to a **Facebook Page**.
2. Create a Meta App at https://developers.facebook.com/apps/. Add the **Facebook Login** and **Instagram Graph API** products.
3. Request the following permissions: `pages_manage_posts`, `pages_read_engagement`, `instagram_basic`, `instagram_content_publish`. Going through Meta App Review is required for production posting.
4. Generate a long-lived Page Access Token: short-lived → User token → exchange for long-lived → derive Page token. Meta's documentation has the exact flow.
5. Find your `META_PAGE_ID` (Page > About) and `META_IG_BUSINESS_ID` (Graph API explorer: `me/accounts` then `{page-id}?fields=instagram_business_account`).

Put `META_APP_ID`, `META_APP_SECRET`, `META_PAGE_ACCESS_TOKEN`, `META_PAGE_ID`, `META_IG_BUSINESS_ID` in `.env`.

## 4. Telegram

1. Talk to [@BotFather](https://t.me/botfather) and create a bot. Save the token.
2. Send any message to your new bot.
3. Find your chat id by visiting `https://api.telegram.org/bot<TOKEN>/getUpdates` and reading the `chat.id` field.

Put `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env`.

## 5. Anthropic

Get an API key from https://console.anthropic.com/. Put `ANTHROPIC_API_KEY` in `.env`.

## 6. Seed your sponsors and style examples

```bash
cp data/sponsors.yaml.example data/sponsors.yaml
$EDITOR data/sponsors.yaml

cp data/style_examples_pt.md.example data/style_examples_pt.md
cp data/style_examples_en.md.example data/style_examples_en.md
$EDITOR data/style_examples_pt.md
$EDITOR data/style_examples_en.md

uv run cycling-agent init-db
uv run cycling-agent seed-sponsors
uv run cycling-agent seed-style --lang pt --path data/style_examples_pt.md
uv run cycling-agent seed-style --lang en --path data/style_examples_en.md
```

## 7. First run (dry-run)

```bash
uv run cycling-agent serve --dry-run
```

In Telegram, send `/start` to your bot. Tag a Strava activity as a Race. Wait for the next poll cycle (default 10 min, or set `POLL_INTERVAL_SECONDS=60` in `.env` for testing). You should receive draft cards.

## 8. Going live

When you trust the loop:

```bash
DRY_RUN=false uv run cycling-agent serve
```

Schedule it to run automatically with your platform's tools (e.g., `systemd --user`, `launchd`, or `tmux`/`screen` for foreground).

## Migration to Raspberry Pi (post-v1)

Same code, same DB; copy `.env` and the `data/` directory; install uv; add a `systemd` unit:

```ini
[Unit]
Description=cycling-social-agent
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/pi/cycling-social-agent
ExecStart=/home/pi/.local/bin/uv run cycling-agent serve
Restart=on-failure

[Install]
WantedBy=default.target
```
```

- [ ] **Step 3: Verify the README renders**

```bash
uv run python -c "from pathlib import Path; print(Path('README.md').read_text())" | head -40
```

- [ ] **Step 4: Lint (markdown is ignored by ruff; verify python files unchanged)**

```bash
uv run ruff check src tests
uv run ty check src tests
uv run pytest -q
```

Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add README.md docs/setup.md
git commit -m "docs: add README and setup guide"
```

---

## Self-review

After all 25 tasks complete, run this final pass:

- [ ] **Step 1: Verify spec coverage**

```bash
uv run pytest -q
```

Expected: all tests pass. Spot-check that each of these spec sections has at least one corresponding test:
- §6.1 cycle loop → integration smoke test (T24)
- §6.2 state machine → repo tests (T5) + smoke test
- §6.3 Telegram approval flow → bot tests (T13)
- §6.4 reflect → reflect tests (T23)
- §7 data model → model tests (T4)
- §8.2 IG image_url-via-FB-album → IG publisher test (T12)
- §9 tool invariants → approval tools sponsor invariant (T15), publish tools status invariants (T16), state tools terminal-state invariant (T17)

- [ ] **Step 2: Final lint + type check**

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run ty check src tests
```

- [ ] **Step 3: Hand-test the dry-run loop with a real Telegram bot**

Use a throwaway bot + a Strava test activity that you tag as a Race. Verify:
- A draft arrives in Telegram with the route map (or stats card if no polyline) and caption.
- Tapping "Approve & post now" results in the agent logging a dry-run publish on the next cycle.
- Tapping "Reject" terminates the draft.
- Tapping "Regenerate" prompts for a hint and produces a new draft on the next cycle.

- [ ] **Step 4: Tag v0.1.0**

```bash
git tag -a v0.1.0 -m "v0.1.0: initial cycling-social-agent"
```

