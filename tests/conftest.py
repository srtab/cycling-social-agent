"""Pytest fixtures shared across all tests."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip real secrets so tests never accidentally hit live services."""
    for key in (
        "STRAVA_CLIENT_ID",
        "STRAVA_CLIENT_SECRET",
        "STRAVA_REFRESH_TOKEN",
        "META_APP_ID",
        "META_APP_SECRET",
        "META_PAGE_ACCESS_TOKEN",
        "TELEGRAM_BOT_TOKEN",
        "ANTHROPIC_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv(key, "test-" + key.lower())
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("DB_PATH", ":memory:")
