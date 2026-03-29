"""YAML configuration loading with dataclass mapping."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ProjectConfig:
    name: str = "refactoring-project"
    target_repo: str = "."
    output_dir: str = "output"
    increments_dir: str = "increments"
    devlogs_dir: str = "devlogs"


@dataclass
class SnapshotConfig:
    include_patterns: list[str] = field(default_factory=lambda: ["*.py"])
    exclude_patterns: list[str] = field(
        default_factory=lambda: ["__pycache__", ".git", "*.pyc", "node_modules"]
    )
    metrics_backend: str = "radon"  # "radon" | "lizard" | "both"


@dataclass
class ExecuteConfig:
    default_model: str = "claude-sonnet-4-20250514"
    cost_per_input_token: float = 0.000003
    cost_per_output_token: float = 0.000015


@dataclass
class TestConfig:
    default_command: str = "pytest tests/ -v"
    working_directory: str | None = None
    timeout_seconds: int = 300


@dataclass
class ReportConfig:
    template_dir: str | None = None
    diff_style: str = "side-by-side"  # "side-by-side" | "unified"
    max_diff_lines: int = 500
    include_source_in_report: bool = True


@dataclass
class ArchiveConfig:
    ledger_backend: str = "json"  # "json" | "sqlite"
    ledger_path: str = "output/ledger.json"


@dataclass
class AppConfig:
    project: ProjectConfig = field(default_factory=ProjectConfig)
    snapshot: SnapshotConfig = field(default_factory=SnapshotConfig)
    execute: ExecuteConfig = field(default_factory=ExecuteConfig)
    test: TestConfig = field(default_factory=TestConfig)
    report: ReportConfig = field(default_factory=ReportConfig)
    archive: ArchiveConfig = field(default_factory=ArchiveConfig)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def find_project_root() -> Path:
    """Walk up from this file's directory until we find pyproject.toml."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    return Path(__file__).resolve().parent.parent.parent


def _build_dataclass(cls: type, data: dict[str, Any] | None):
    """Recursively construct a dataclass from a dict, handling nested dataclasses."""
    if data is None:
        return cls()

    import typing

    try:
        resolved_hints = typing.get_type_hints(cls)
    except Exception:
        resolved_hints = {}

    kwargs: dict[str, Any] = {}

    for key, value in data.items():
        if key not in cls.__dataclass_fields__:
            continue

        expected = resolved_hints.get(key)

        if isinstance(expected, type) and hasattr(expected, "__dataclass_fields__"):
            kwargs[key] = _build_dataclass(expected, value)
        else:
            kwargs[key] = value

    return cls(**kwargs)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_config(path: str | None = None) -> AppConfig:
    """Load YAML configuration and return a fully-constructed AppConfig.

    Parameters
    ----------
    path : str or None
        Path to the YAML config file. When *None*, defaults to
        ``config/default.yaml`` relative to the project root.
    """
    if path is None:
        config_path = find_project_root() / "config" / "default.yaml"
    else:
        config_path = Path(path)

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, "r") as fh:
        raw: dict[str, Any] = yaml.safe_load(fh) or {}

    return _build_dataclass(AppConfig, raw)
