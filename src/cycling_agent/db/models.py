"""ORM models for the cycling agent.

State machines:
- Activity: detected -> drafting -> awaiting_approval -> processed
- Draft: pending -> drafted -> awaiting_approval -> approved -> scheduled -> published
                                                          -> rejected | editing | regenerating
"""

from __future__ import annotations

import datetime as dt
import enum

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


class Platform(enum.StrEnum):
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"


class Language(enum.StrEnum):
    PT = "pt"
    EN = "en"


class ActivityStatus(enum.StrEnum):
    DETECTED = "detected"
    DRAFTING = "drafting"
    AWAITING_APPROVAL = "awaiting_approval"
    PROCESSED = "processed"


class DraftStatus(enum.StrEnum):
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
    feeling_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ActivityStatus] = mapped_column(
        String(32), default=ActivityStatus.DETECTED, nullable=False
    )
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now, nullable=False)
    processed_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)

    drafts: Mapped[list[Draft]] = relationship(back_populates="activity", cascade="all, delete-orphan")


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
    hashtags: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_paths: Mapped[str | None] = mapped_column(Text, nullable=True)  # comma-separated
    status: Mapped[DraftStatus] = mapped_column(
        String(32), default=DraftStatus.PENDING, nullable=False
    )
    telegram_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    regenerate_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    scheduled_for: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
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
    handle_facebook: Mapped[str | None] = mapped_column(String(255), nullable=True)
    handle_instagram: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hashtag: Mapped[str | None] = mapped_column(String(255), nullable=True)


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
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    tool_call_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_estimate_usd: Mapped[float] = mapped_column(default=0.0, nullable=False)
    outcome: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)


class ApprovalEvent(Base):
    __tablename__ = "approval_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("drafts.id"), nullable=False)
    event: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now, nullable=False)
