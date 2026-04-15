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
