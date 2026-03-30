"""Rich-based logging setup with optional per-increment file logging."""

from __future__ import annotations

import logging
from pathlib import Path

from rich.logging import RichHandler

LOGGER_NAME = "refactor_framework"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

_file_handler: logging.FileHandler | None = None


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure and return the application logger with Rich output."""
    logger = logging.getLogger(LOGGER_NAME)
    if not logger.handlers:
        handler = RichHandler(rich_tracebacks=True, show_path=False)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    return logger


def setup_increment_logging(increment_id: str, increments_dir: str) -> None:
    """Add a FileHandler that writes to increments/<id>/log.txt."""
    global _file_handler
    logger = logging.getLogger(LOGGER_NAME)

    # Remove previous file handler if any
    if _file_handler and _file_handler in logger.handlers:
        logger.removeHandler(_file_handler)

    log_path = Path(increments_dir) / increment_id / "log.txt"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    _file_handler = logging.FileHandler(str(log_path), mode="a", encoding="utf-8")
    _file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(_file_handler)
