"""Media rendering tools."""

from __future__ import annotations

from pathlib import Path

from langchain_core.tools import BaseTool, tool

from cycling_agent.db.repo import Repository
from cycling_agent.media.route_map import RouteMapRenderer
from cycling_agent.media.stats_card import StatsCardRenderer
from cycling_agent.strava.client import StravaClient


def build_media_tools(*, repo: Repository, strava: StravaClient, media_dir: Path) -> list[BaseTool]:
    stats_card = StatsCardRenderer()
    route_map = RouteMapRenderer()

    def _path(activity_id: int, kind: str) -> Path:
        out_dir = media_dir / str(activity_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir / f"{kind}.png"

    @tool
    def render_stats_card(activity_id: int) -> str:
        """Render a stats card PNG for an activity. Returns the file path."""
        a = strava.get_activity_detail(activity_id)
        path = _path(activity_id, "stats")
        stats_card.render(a, path)
        return str(path)

    @tool
    def render_route_map(activity_id: int) -> str:
        """Render a route map PNG for an activity. Returns the file path."""
        a = strava.get_activity_detail(activity_id)
        if not a.polyline:
            raise ValueError(f"activity {activity_id} has no polyline")
        path = _path(activity_id, "map")
        route_map.render(polyline=a.polyline, out_path=path)
        return str(path)

    return [render_stats_card, render_route_map]
