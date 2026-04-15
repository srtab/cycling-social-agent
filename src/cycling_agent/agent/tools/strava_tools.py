"""Tools the agent uses to interact with Strava and the activities table."""

from __future__ import annotations

import datetime as dt

from langchain_core.tools import BaseTool, tool

from cycling_agent.db.models import ActivityStatus
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
