"""Tests for the strava poller."""

from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock

import pytest

from cycling_agent.db.engine import build_engine, build_session_factory, init_schema
from cycling_agent.db.repo import Repository
from cycling_agent.strava.client import StravaActivity
from cycling_agent.strava.poller import StravaPoller


@pytest.fixture()
def repo() -> Repository:
    engine = build_engine(":memory:")
    init_schema(engine)
    return Repository(build_session_factory(engine))


def _race(id_: int) -> StravaActivity:
    return StravaActivity(
        id=id_, name=f"Race {id_}", workout_type=11,
        started_at=dt.datetime(2026, 4, 1, 10, 0, tzinfo=dt.UTC),
        distance_m=100000, moving_time_s=10000, elevation_gain_m=1500,
        avg_speed_mps=10.0, avg_power_w=300, norm_power_w=305, avg_hr=160,
        max_hr=185, kilojoules=3000, feeling_text=None, polyline="abc",
    )


def test_poll_inserts_new_races(repo: Repository) -> None:
    fake_strava = MagicMock()
    fake_strava.list_recent_races.return_value = [_race(1), _race(2)]
    poller = StravaPoller(client=fake_strava, repo=repo, lookback_days=7)
    new_ids = poller.poll(now=dt.datetime(2026, 4, 1, 12, 0, tzinfo=dt.UTC))
    assert sorted(new_ids) == [1, 2]


def test_poll_skips_already_known(repo: Repository) -> None:
    fake_strava = MagicMock()
    fake_strava.list_recent_races.return_value = [_race(1)]
    poller = StravaPoller(client=fake_strava, repo=repo, lookback_days=7)
    poller.poll(now=dt.datetime(2026, 4, 1, 12, 0, tzinfo=dt.UTC))
    new_ids = poller.poll(now=dt.datetime(2026, 4, 1, 12, 30, tzinfo=dt.UTC))
    assert new_ids == []


def test_poll_passes_lookback_to_client(repo: Repository) -> None:
    fake_strava = MagicMock()
    fake_strava.list_recent_races.return_value = []
    poller = StravaPoller(client=fake_strava, repo=repo, lookback_days=3)
    now = dt.datetime(2026, 4, 1, 12, 0, tzinfo=dt.UTC)
    poller.poll(now=now)
    fake_strava.list_recent_races.assert_called_once()
    after = fake_strava.list_recent_races.call_args.kwargs["after"]
    assert after == now - dt.timedelta(days=3)
