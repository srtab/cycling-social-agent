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
