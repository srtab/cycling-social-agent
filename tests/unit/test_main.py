"""Tests for main entry wiring (no real network)."""

from __future__ import annotations

import pytest

from cycling_agent.config import Settings
from cycling_agent.db.models import Platform
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

    assert Platform.FACEBOOK in publishers
    assert Platform.INSTAGRAM in publishers
    from cycling_agent.publishers.facebook import FacebookPublisher
    from cycling_agent.publishers.instagram import InstagramPublisher

    assert isinstance(publishers[Platform.FACEBOOK], FacebookPublisher)
    assert isinstance(publishers[Platform.INSTAGRAM], InstagramPublisher)


@pytest.mark.parametrize(
    ("enabled", "expected"),
    [
        ("facebook", {Platform.FACEBOOK}),
        ("instagram", {Platform.INSTAGRAM}),
        ("facebook,instagram", {Platform.FACEBOOK, Platform.INSTAGRAM}),
    ],
)
def test_build_publishers_respects_enabled_platforms(enabled: str, expected: set[Platform]) -> None:
    settings = Settings()
    settings.dry_run = True
    settings.enabled_platforms = enabled
    publishers = build_publishers(settings)
    assert set(publishers.keys()) == expected


def test_settings_rejects_unknown_platform() -> None:
    with pytest.raises(ValueError, match="unknown platforms"):
        Settings(enabled_platforms="facebook,tiktok")


def test_settings_rejects_empty_platform_list() -> None:
    with pytest.raises(ValueError, match="at least one platform"):
        Settings(enabled_platforms=" , ")
