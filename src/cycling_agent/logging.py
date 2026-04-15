"""Application-wide logging configuration using structlog over stdlib logging."""

from __future__ import annotations

import logging
import sys

import structlog
from rich.console import Console
from rich.logging import RichHandler

_VALID_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def configure_logging(level: str) -> None:
    """Configure stdlib + structlog with rich console output.

    Idempotent: safe to call more than once (e.g., reconfiguring in tests).
    """
    if level not in _VALID_LEVELS:
        raise ValueError(f"invalid log level: {level}")

    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=Console(file=sys.stderr), rich_tracebacks=True)],
        force=True,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level)),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Convenience accessor matching the stdlib pattern."""
    return structlog.get_logger(name)
