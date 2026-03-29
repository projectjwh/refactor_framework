"""Path helpers and directory management."""

from __future__ import annotations

from pathlib import Path

from refactor_framework.config import find_project_root


def get_increments_dir(config_increments_dir: str = "increments") -> Path:
    """Return the absolute path to the increments directory."""
    root = find_project_root()
    return root / config_increments_dir


def get_output_dir(config_output_dir: str = "output") -> Path:
    """Return the absolute path to the output directory."""
    root = find_project_root()
    return root / config_output_dir


def get_increment_path(increment_id: str, config_increments_dir: str = "increments") -> Path:
    """Return the path for a specific increment."""
    return get_increments_dir(config_increments_dir) / increment_id


def ensure_dir(path: Path) -> Path:
    """Create directory (and parents) if it doesn't exist, return the path."""
    path.mkdir(parents=True, exist_ok=True)
    return path
