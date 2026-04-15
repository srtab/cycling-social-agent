"""Strava API wrapper.

Wraps stravalib so the rest of the codebase only sees our typed
``StravaActivity`` dataclass. OAuth token refresh is delegated to
stravalib via ``refresh_access_token``; we cache the access token in
memory for the process lifetime.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import enum
import time
from typing import Any

import structlog
from stravalib import Client as StravalibClient

log = structlog.get_logger(__name__)


class RaceCodes(int, enum.Enum):
    """Strava workout_type integer codes that mean 'race'."""

    RIDE = 11
    RUN = 1


@dataclasses.dataclass(frozen=True)
class StravaActivity:
    id: int
    name: str
    workout_type: int
    started_at: dt.datetime
    distance_m: float
    moving_time_s: int
    elevation_gain_m: float
    avg_speed_mps: float
    avg_power_w: float | None
    norm_power_w: float | None
    avg_hr: float | None
    max_hr: float | None
    kilojoules: float | None
    feeling_text: str | None
    polyline: str | None


class StravaClient:
    """High-level Strava client used by the rest of the app."""

    def __init__(
        self,
        *,
        client: StravalibClient | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        refresh_token: str | None = None,
    ) -> None:
        self._client = client or StravalibClient()
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._access_token_expires_at: float = 0.0

    def _ensure_token(self) -> None:
        if self._client_id is None:
            return  # tests inject a pre-built client
        if time.time() < self._access_token_expires_at - 60:
            return
        token_data = self._client.refresh_access_token(
            client_id=int(self._client_id),
            client_secret=self._client_secret,
            refresh_token=self._refresh_token,
        )
        self._client.access_token = token_data["access_token"]
        self._refresh_token = token_data["refresh_token"]
        self._access_token_expires_at = float(token_data["expires_at"])
        log.info("strava.token_refreshed", expires_at=self._access_token_expires_at)

    # --- classmethods used directly by tools ---------------------------------

    @classmethod
    def is_race(cls, payload: Any) -> bool:
        """True iff workout_type matches one of the race codes for the sport."""
        sport = _attr(payload, "sport_type", _attr(payload, "type", None))
        wt = _attr(payload, "workout_type", None)
        if wt is None:
            return False
        if sport == "Run":
            return wt == RaceCodes.RUN.value
        # Default to Ride
        return wt == RaceCodes.RIDE.value

    @classmethod
    def to_activity(cls, payload: Any) -> StravaActivity:
        """Convert raw Strava payload (dict or attr-object) into our typed activity."""
        started = _attr(payload, "start_date_local")
        # ISO-8601 may end in Z; stravalib already returns datetime objects.
        started_dt = (
            dt.datetime.fromisoformat(started.replace("Z", "+00:00"))
            if isinstance(started, str)
            else started
        )
        if started_dt.tzinfo is None:
            started_dt = started_dt.replace(tzinfo=dt.UTC)

        map_obj = _attr(payload, "map", None)
        polyline = _attr(map_obj, "summary_polyline", None) if map_obj is not None else None

        return StravaActivity(
            id=int(_attr(payload, "id")),
            name=str(_attr(payload, "name", "")),
            workout_type=int(_attr(payload, "workout_type", 0) or 0),
            started_at=started_dt,
            distance_m=float(_attr(payload, "distance", 0.0) or 0.0),
            moving_time_s=int(_attr(payload, "moving_time", 0) or 0),
            elevation_gain_m=float(_attr(payload, "total_elevation_gain", 0.0) or 0.0),
            avg_speed_mps=float(_attr(payload, "average_speed", 0.0) or 0.0),
            avg_power_w=_optional_float(_attr(payload, "average_watts", None)),
            norm_power_w=_optional_float(_attr(payload, "weighted_average_watts", None)),
            avg_hr=_optional_float(_attr(payload, "average_heartrate", None)),
            max_hr=_optional_float(_attr(payload, "max_heartrate", None)),
            kilojoules=_optional_float(_attr(payload, "kilojoules", None)),
            feeling_text=_optional_str(_attr(payload, "description", None)),
            polyline=polyline,
        )

    # --- instance methods ----------------------------------------------------

    def list_recent_races(self, *, after: dt.datetime) -> list[StravaActivity]:
        """List race activities started after the given UTC timestamp."""
        self._ensure_token()
        results: list[StravaActivity] = []
        for raw in self._client.get_activities(after=after):
            if self.is_race(raw):
                results.append(self.to_activity(raw))
        return results

    def get_activity_detail(self, activity_id: int) -> StravaActivity:
        """Fetch full activity detail (including description) by id."""
        self._ensure_token()
        raw = self._client.get_activity(activity_id, include_all_efforts=True)
        return self.to_activity(raw)


def _attr(obj: Any, key: str, default: Any = None) -> Any:
    """Resolve attribute or dict-key access with a default."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _optional_float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    return float(v)


def _optional_str(v: Any) -> str | None:
    if v is None or v == "":
        return None
    return str(v)
