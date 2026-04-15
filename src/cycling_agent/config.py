"""Typed application settings sourced from environment variables and `.env`."""

from __future__ import annotations

import re

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from cycling_agent.db.models import Platform

_HHMM = re.compile(r"^\d{2}:\d{2}$")


class Settings(BaseSettings):
    """All runtime configuration. Read from `.env` then process env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # External services
    strava_client_id: str = ""
    strava_client_secret: str = ""
    strava_refresh_token: str = ""
    strava_athlete_id: str = ""

    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_page_access_token: str = ""
    meta_page_id: str = ""
    meta_ig_business_id: str = ""

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    anthropic_api_key: str = ""

    # LangSmith (observability). Consumed by the langchain/langsmith SDK via
    # os.environ, not by our code — declared here for discoverability and so
    # ``load_dotenv`` at startup populates them alongside the other secrets.
    langsmith_tracing: bool = False
    langsmith_project: str = "cycling-social-agent"
    langsmith_api_key: str = ""

    # Runtime
    poll_interval_seconds: int = Field(default=600, ge=60)
    orchestrator_model: str = "claude-haiku-4-5-20251001"
    drafter_model: str = "claude-sonnet-4-6"
    reflector_model: str = "claude-sonnet-4-6"
    db_path: str = "./data/cycling.db"
    dry_run: bool = False
    log_level: str = "INFO"

    # Scheduling
    publish_time_local: str = "19:00"
    publish_timezone: str = "Europe/Lisbon"

    # Platforms — comma-separated list of platforms to publish to. Set to e.g.
    # ``facebook`` to temporarily pause Instagram without removing code.
    enabled_platforms: str = "facebook,instagram"

    @field_validator("publish_time_local")
    @classmethod
    def _validate_publish_time(cls, v: str) -> str:
        if not _HHMM.match(v):
            raise ValueError("PUBLISH_TIME_LOCAL must be HH:MM")
        hh, mm = v.split(":")
        if not (0 <= int(hh) < 24 and 0 <= int(mm) < 60):
            raise ValueError("PUBLISH_TIME_LOCAL must be HH:MM with valid hour/minute")
        return v

    @field_validator("enabled_platforms")
    @classmethod
    def _validate_enabled_platforms(cls, v: str) -> str:
        tokens = [t.strip() for t in v.split(",") if t.strip()]
        if not tokens:
            raise ValueError("ENABLED_PLATFORMS must list at least one platform")
        valid = {p.value for p in Platform}
        invalid = [t for t in tokens if t not in valid]
        if invalid:
            raise ValueError(f"ENABLED_PLATFORMS has unknown platforms: {invalid}. Valid: {sorted(valid)}")
        return v

    @property
    def enabled_platform_set(self) -> set[Platform]:
        """Parsed view of ``enabled_platforms`` as a set of ``Platform`` values."""
        return {Platform(t.strip()) for t in self.enabled_platforms.split(",") if t.strip()}


def load_settings() -> Settings:
    """Module-level loader so tests can override via monkeypatching env.

    Also populates ``os.environ`` from ``.env`` so third-party SDKs
    (``ChatAnthropic``, ``stravalib``, etc.) that read env vars directly
    see the same values as ``Settings``.
    """
    from dotenv import load_dotenv

    load_dotenv(override=False)
    return Settings()
