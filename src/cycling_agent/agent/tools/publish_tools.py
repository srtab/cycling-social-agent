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
        # SQLAlchemy returns enum columns as plain strings; compare via StrEnum equality.
        if d.status not in (DraftStatus.SCHEDULED, DraftStatus.APPROVED):
            return f"REJECTED: draft {draft_id} status is {d.status}, not approved/scheduled"
        if d.status == DraftStatus.APPROVED and not d.post_now:
            return f"REJECTED: draft {draft_id} approved but not marked post_now; use schedule_publish"

        platform = Platform(d.platform)
        publisher = publishers[platform]
        request = PublishRequest(
            caption=(d.caption + ("\n" + d.hashtags if d.hashtags else "")).strip(),
            media_paths=[Path(p) for p in (d.media_paths or "").split(",") if p],
        )
        external_id = publisher.publish(request)
        repo.record_post(draft_id=draft_id, platform=platform, external_post_id=external_id)
        return external_id

    @tool
    def schedule_publish(draft_id: int) -> str:
        """Move an approved draft to scheduled state with the next publish window."""
        d = repo.get_draft(draft_id)
        if d is None:
            return f"REJECTED: draft {draft_id} not found"
        if d.status != DraftStatus.APPROVED:
            return f"REJECTED: draft {draft_id} status is {d.status}, not approved"
        if d.post_now:
            return (
                f"REJECTED: draft {draft_id} is post_now; "
                f"do not schedule, call publish_due_drafts instead"
            )
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
                published_ids.append(f"{d.platform}:{external}")
            except Exception as e:
                published_ids.append(f"{d.platform}:ERROR:{e}")
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
