"""Tests for the typed config loader."""

from __future__ import annotations

import pytest

from cycling_agent.config import Settings


def test_settings_load_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLL_INTERVAL_SECONDS", "300")
    monkeypatch.setenv("PUBLISH_TIME_LOCAL", "20:30")
    monkeypatch.setenv("PUBLISH_TIMEZONE", "Europe/Lisbon")
    monkeypatch.setenv("DRY_RUN", "true")

    settings = Settings()

    assert settings.poll_interval_seconds == 300
    assert settings.publish_time_local == "20:30"
    assert settings.publish_timezone == "Europe/Lisbon"
    assert settings.dry_run is True


def test_settings_publish_time_validates_format(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PUBLISH_TIME_LOCAL", "not-a-time")
    with pytest.raises(ValueError, match="HH:MM"):
        Settings()


def test_settings_default_models() -> None:
    settings = Settings()
    assert "haiku" in settings.orchestrator_model.lower()
    assert "sonnet" in settings.drafter_model.lower()
