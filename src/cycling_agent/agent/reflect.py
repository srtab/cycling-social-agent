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
