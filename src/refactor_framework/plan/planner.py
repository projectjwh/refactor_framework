"""Increment plan creation and validation."""

from __future__ import annotations

import fnmatch
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import yaml

from refactor_framework.config import AppConfig
from refactor_framework.models import (
    ConstructMapping,
    IncrementPlan,
    IncrementRecord,
    MigrationConfig,
)
from refactor_framework.utils.ids import generate_increment_id
from refactor_framework.utils.paths import ensure_dir

logger = logging.getLogger("refactor_framework.plan")


def resolve_files(target_repo: str, patterns: list[str]) -> list[str]:
    """Resolve glob patterns against the target repo, returning relative paths."""
    repo = Path(target_repo)
    if not repo.is_dir():
        raise FileNotFoundError(f"Target repo not found: {target_repo}")

    matched: set[str] = set()
    for pattern in patterns:
        for path in repo.rglob("*"):
            if path.is_file() and fnmatch.fnmatch(path.name, pattern):
                matched.add(str(path.relative_to(repo)))

    return sorted(matched)


def create_plan(
    config: AppConfig,
    file_patterns: list[str],
    description: str,
    criteria: list[str] | None = None,
    target_patterns: list[str] | None = None,
    source_repo: str | None = None,
    source_patterns: list[str] | None = None,
    mode: str = "same-language",
) -> IncrementRecord:
    """Create a new increment plan.

    For cross-language mode, source_repo and source_patterns specify the legacy
    codebase. file_patterns resolve against config.project.target_repo as usual.
    """
    increment_id = generate_increment_id()
    resolved = resolve_files(config.project.target_repo, file_patterns)

    if not resolved:
        raise ValueError(
            f"No files matched patterns {file_patterns} in {config.project.target_repo}"
        )

    # Resolve source files for cross-language mode
    source_files = []
    migration = MigrationConfig(mode=mode)

    if source_repo and mode == "cross-language":
        migration.source_repo = str(Path(source_repo).resolve())
        if source_patterns:
            source_files = resolve_files(source_repo, source_patterns)
        # Auto-detect languages from file extensions
        from refactor_framework.snapshot.metrics import detect_language

        if source_files:
            migration.source_language = detect_language(source_files[0])
        if resolved:
            migration.target_language = detect_language(resolved[0])

    plan = IncrementPlan(
        increment_id=increment_id,
        description=description,
        target_files=resolved,
        target_patterns=target_patterns or [],
        acceptance_criteria=criteria or [],
        created_at=datetime.now(timezone.utc).isoformat(),
        source_files=source_files,
        migration=migration,
    )

    record = IncrementRecord(
        increment_id=increment_id,
        status="planned",
        plan=plan,
    )

    inc_dir = ensure_dir(Path(config.project.increments_dir) / increment_id)
    plan_file = inc_dir / "plan.yaml"
    plan_file.write_text(
        yaml.dump(_plan_to_dict(plan), default_flow_style=False, sort_keys=False)
    )

    logger.info("Created increment %s with %d files (mode=%s)", increment_id, len(resolved), mode)
    return record


def load_plan(increments_dir: str, increment_id: str) -> IncrementPlan:
    """Load an existing plan from its increment directory."""
    plan_file = Path(increments_dir) / increment_id / "plan.yaml"
    if not plan_file.exists():
        raise FileNotFoundError(f"Plan not found: {plan_file}")

    data = yaml.safe_load(plan_file.read_text())

    # Deserialize construct_mappings
    mappings_raw = data.get("construct_mappings", [])
    mappings = [ConstructMapping(**m) for m in mappings_raw] if mappings_raw else []

    # Deserialize migration config
    mig_raw = data.get("migration", {})
    migration = MigrationConfig(**mig_raw) if mig_raw else MigrationConfig()

    return IncrementPlan(
        increment_id=data.get("increment_id", increment_id),
        description=data.get("description", ""),
        target_files=data.get("target_files", []),
        target_patterns=data.get("target_patterns", []),
        acceptance_criteria=data.get("acceptance_criteria", []),
        created_at=data.get("created_at", ""),
        source_files=data.get("source_files", []),
        construct_mappings=mappings,
        migration=migration,
    )


def save_plan(increments_dir: str, increment_id: str, plan: IncrementPlan) -> None:
    """Save an updated plan back to its increment directory."""
    plan_file = Path(increments_dir) / increment_id / "plan.yaml"
    plan_file.write_text(
        yaml.dump(_plan_to_dict(plan), default_flow_style=False, sort_keys=False)
    )


def _plan_to_dict(plan: IncrementPlan) -> dict:
    """Convert plan to a clean dict for YAML serialization."""
    d = {
        "increment_id": plan.increment_id,
        "description": plan.description,
        "target_files": plan.target_files,
        "target_patterns": plan.target_patterns,
        "acceptance_criteria": plan.acceptance_criteria,
        "created_at": plan.created_at,
    }
    if plan.source_files:
        d["source_files"] = plan.source_files
    if plan.construct_mappings:
        d["construct_mappings"] = [
            _mapping_to_dict(m) for m in plan.construct_mappings
        ]
    if plan.migration.mode != "same-language":
        d["migration"] = asdict(plan.migration)
    return d


def _mapping_to_dict(m: ConstructMapping) -> dict:
    """Convert a ConstructMapping to a clean dict for YAML."""
    d = {
        "source_file": m.source_file,
        "source_construct": m.source_construct,
        "source_language": m.source_language,
        "target_file": m.target_file,
        "target_construct": m.target_construct,
        "target_language": m.target_language,
        "mapping_type": m.mapping_type,
        "status": m.status,
        "description": m.description,
    }
    if m.source_line_start is not None:
        d["source_line_start"] = m.source_line_start
    if m.source_line_end is not None:
        d["source_line_end"] = m.source_line_end
    if m.target_line_start is not None:
        d["target_line_start"] = m.target_line_start
    if m.target_line_end is not None:
        d["target_line_end"] = m.target_line_end
    return d
