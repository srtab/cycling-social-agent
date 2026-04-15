"""Tests for the Strava client wrapper."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from cycling_agent.strava.client import RaceCodes, StravaActivity, StravaClient

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures"


@pytest.fixture()
def race_payload() -> dict:
    return json.loads((FIXTURE_DIR / "strava_race_activity.json").read_text())


@pytest.fixture()
def training_payload() -> dict:
    return json.loads((FIXTURE_DIR / "strava_training_ride.json").read_text())


def _attr_dict(d: dict):
    """Stravalib returns objects with attributes; emulate with a SimpleNamespace."""
    obj = SimpleNamespace(**d)
    if "map" in d and isinstance(d["map"], dict):
        obj.map = SimpleNamespace(**d["map"])
    return obj


def test_is_race_returns_true_for_ride_workout_type_11(race_payload: dict) -> None:
    assert StravaClient.is_race(race_payload) is True


def test_is_race_returns_false_for_endurance_ride(training_payload: dict) -> None:
    assert StravaClient.is_race(training_payload) is False


def test_is_race_handles_run_workout_type_1() -> None:
    assert StravaClient.is_race({"sport_type": "Run", "workout_type": 1}) is True


def test_to_activity_extracts_feeling_from_description(race_payload: dict) -> None:
    a = StravaClient.to_activity(race_payload)
    assert isinstance(a, StravaActivity)
    assert a.id == 14738291734
    assert "ataquei" in (a.feeling_text or "")
    assert a.workout_type == RaceCodes.RIDE


def test_to_activity_normalises_started_at(race_payload: dict) -> None:
    a = StravaClient.to_activity(race_payload)
    assert a.started_at == dt.datetime(2026, 2, 19, 13, 30, 0, tzinfo=dt.UTC)


def test_to_activity_handles_missing_description(training_payload: dict) -> None:
    a = StravaClient.to_activity(training_payload)
    assert a.feeling_text is None or a.feeling_text == ""


def test_list_recent_activities_filters_to_races(race_payload: dict, training_payload: dict) -> None:
    fake_strava = MagicMock()
    fake_strava.get_activities.return_value = [
        _attr_dict(race_payload),
        _attr_dict(training_payload),
    ]
    client = StravaClient(client=fake_strava)
    races = client.list_recent_races(after=dt.datetime(2026, 1, 1, tzinfo=dt.UTC))
    assert [r.id for r in races] == [14738291734]


def test_get_activity_detail_calls_stravalib(race_payload: dict) -> None:
    fake_strava = MagicMock()
    fake_strava.get_activity.return_value = _attr_dict(race_payload)
    client = StravaClient(client=fake_strava)
    a = client.get_activity_detail(14738291734)
    fake_strava.get_activity.assert_called_once_with(14738291734, include_all_efforts=True)
    assert a.id == 14738291734
