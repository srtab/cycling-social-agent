"""Strava poller: fetch recent race activities and persist new ones to the DB."""

from __future__ import annotations

import datetime as dt

import structlog

from cycling_agent.db.repo import Repository
from cycling_agent.strava.client import StravaClient

log = structlog.get_logger(__name__)


class StravaPoller:
    """Glue between :class:`StravaClient` and the :class:`Repository`."""

    def __init__(self, *, client: StravaClient, repo: Repository, lookback_days: int = 7) -> None:
        self._client = client
        self._repo = repo
        self._lookback = dt.timedelta(days=lookback_days)

    def poll(self, *, now: dt.datetime) -> list[int]:
        """Fetch races from `now - lookback_days` and upsert any new ones.

        Returns the list of activity ids that were *newly* inserted.
        """
        races = self._client.list_recent_races(after=now - self._lookback)
        log.info("strava.poll.found", count=len(races))

        new_ids: list[int] = []
        for r in races:
            existing = self._repo.get_activity(r.id)
            self._repo.upsert_activity(
                id=r.id,
                started_at=r.started_at.replace(tzinfo=None),
                name=r.name,
                workout_type=r.workout_type,
            )
            if existing is None:
                new_ids.append(r.id)
                log.info("strava.poll.new_race", id=r.id, name=r.name)

        return new_ids
