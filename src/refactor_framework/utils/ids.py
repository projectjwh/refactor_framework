"""Increment ID generation and validation."""

from __future__ import annotations

import re
from datetime import datetime

_ID_PATTERN = re.compile(r"^\d{8}T\d{6}$")


def generate_increment_id() -> str:
    """Generate an increment ID from the current timestamp (e.g., 20260326T143022)."""
    return datetime.now().strftime("%Y%m%dT%H%M%S")


def validate_increment_id(increment_id: str) -> bool:
    """Check whether a string is a valid increment ID."""
    return bool(_ID_PATTERN.match(increment_id))
