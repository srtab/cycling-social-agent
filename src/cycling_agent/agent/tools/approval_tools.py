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
        repo.set_draft_status(draft_id, DraftStatus.AWAITING_APPROVAL, telegram_message_id=message_id)
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
