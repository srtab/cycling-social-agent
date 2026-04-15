"""Tests for main entry wiring (no real network)."""

from __future__ import annotations

from cycling_agent.config import Settings
from cycling_agent.main import build_publishers, build_strava


def test_build_strava_returns_configured_client() -> None:
    settings = Settings()
    settings.strava_client_id = "1"
    settings.strava_client_secret = "secret"
    settings.strava_refresh_token = "refresh"
    client = build_strava(settings)
    assert client is not None


def test_build_publishers_dry_run_returns_both() -> None:
    settings = Settings()
    settings.dry_run = True
    publishers = build_publishers(settings)
    from cycling_agent.db.models import Platform

    assert Platform.FACEBOOK in publishers
    assert Platform.INSTAGRAM in publishers
    from cycling_agent.publishers.facebook import FacebookPublisher
    from cycling_agent.publishers.instagram import InstagramPublisher

    assert isinstance(publishers[Platform.FACEBOOK], FacebookPublisher)
    assert isinstance(publishers[Platform.INSTAGRAM], InstagramPublisher)
