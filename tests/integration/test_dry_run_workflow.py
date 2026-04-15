"""End-to-end smoke test of the workflow with the LLM orchestrator stubbed out.

We exercise the tools directly in the order the orchestrator would, to verify
the tool layer integrates correctly. The drafter sub-agent is not invoked;
we feed a hand-written caption that satisfies the sponsor invariant.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from cycling_agent.agent.tools.approval_tools import build_approval_tools
from cycling_agent.agent.tools.content_tools import build_content_tools
from cycling_agent.agent.tools.media_tools import build_media_tools
from cycling_agent.agent.tools.publish_tools import build_publish_tools
from cycling_agent.agent.tools.state_tools import build_state_tools
from cycling_agent.agent.tools.strava_tools import build_strava_tools
from cycling_agent.db.engine import build_engine, build_session_factory, init_schema
from cycling_agent.db.models import ActivityStatus, DraftStatus, Platform, Sponsor
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
    # confirm content tools loaded (sponsors visible)
    sponsor_text = by_name(content_tools, "read_sponsors").invoke({})
    assert "BrandX" in sponsor_text

    caption = "Etapa difícil mas valeu. Obrigado @brandx pelo apoio. #brandx"
    result = by_name(approval_tools, "send_for_approval").invoke({
        "activity_id": 14738291734, "platform": "facebook", "language": "pt",
        "caption": caption, "hashtags": "", "media_paths": stats_path,
    })
    assert "Sent" in result

    # --- step 5: simulate rider tapping "Approve & post now" --------------
    drafts = repo.list_drafts_in_states([DraftStatus.AWAITING_APPROVAL])
    assert len(drafts) == 1
    draft_id = drafts[0].id
    repo.set_approved(draft_id, post_now=True)

    # --- step 6: publish_due_drafts ----------------------------------------
    published = by_name(publish_tools, "publish_due_drafts").invoke({})
    assert "facebook:dry-run-fb-" in published

    # --- step 7: mark_processed --------------------------------------------
    out = by_name(state_tools, "mark_processed").invoke({"activity_id": 14738291734})
    assert "processed" in out.lower()

    a = repo.get_activity(14738291734)
    assert a is not None
    assert a.status == ActivityStatus.PROCESSED
