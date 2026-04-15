"""Repository façade over the ORM session.

All write methods commit on success. All read methods are query-only.
Idempotent where the spec requires it (upsert_activity, record_post).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

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

    def get_activity(self, activity_id: int) -> Activity | None:
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
        hashtags: str | None = None,
        media_paths: str | None = None,
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

    def get_draft(self, draft_id: int) -> Draft | None:
        with self._session_factory() as s:
            return s.get(Draft, draft_id)

    def get_draft_by_telegram_message(self, message_id: int) -> Draft | None:
        with self._session_factory() as s:
            stmt = select(Draft).where(Draft.telegram_message_id == message_id)
            return s.execute(stmt).scalar_one_or_none()

    def set_draft_status(
        self,
        draft_id: int,
        status: DraftStatus,
        *,
        telegram_message_id: int | None = None,
        feedback_hint: str | None = None,
        caption: str | None = None,
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
