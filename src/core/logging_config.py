"""
Structured JSON logging via structlog.
Call configure_logging() once at application startup.
"""
from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(level: str = "INFO", *, pretty: bool = False) -> None:
    """
    Configure structlog for the entire process.

    Args:
        level:  Log level string (DEBUG, INFO, WARNING, ERROR).
        pretty: Use dev-friendly coloured console output (not for prod).
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]

    if pretty:
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=shared_processors + [renderer],
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Also configure stdlib logging so third-party libs behave
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=numeric_level,
    )
    # Silence noisy libraries
    for noisy in ("urllib3", "httpx", "httpcore", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
