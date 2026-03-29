"""Rich-based logging setup."""

from __future__ import annotations

import logging

from rich.logging import RichHandler

LOGGER_NAME = "refactor_framework"


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure and return the application logger with Rich output."""
    logger = logging.getLogger(LOGGER_NAME)
    if not logger.handlers:
        handler = RichHandler(rich_tracebacks=True, show_path=False)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    return logger
