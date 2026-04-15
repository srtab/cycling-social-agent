"""Tests for structlog configuration."""

from __future__ import annotations

import logging

import pytest
import structlog

from cycling_agent.logging import configure_logging


def test_configure_logging_sets_level() -> None:
    configure_logging("DEBUG")
    logger = structlog.get_logger("test")
    assert logging.getLogger().level == logging.DEBUG
    # smoke: logger emits without raising
    logger.info("hello", n=1)


def test_configure_logging_invalid_level_raises() -> None:
    with pytest.raises(ValueError, match="invalid log level"):
        configure_logging("NOPE")
