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

    @tool
    def list_drafts_for_activity(activity_id: int) -> str:
        """Return existing drafts for an activity so the orchestrator can decide
        which ``(platform, language)`` combinations still need drafting.

        One line per draft: ``draft_id=<id> platform=<p> language=<l> status=<s>``.
        Returns ``"No drafts."`` if there are none.
        """
        drafts = repo.list_drafts_for_activity(activity_id)
        if not drafts:
            return "No drafts."
        return "\n".join(
            f"draft_id={d.id} platform={d.platform} language={d.language} status={d.status}" for d in drafts
        )

    return [mark_processed, log_feedback, list_drafts_for_activity]
