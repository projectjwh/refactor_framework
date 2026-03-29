"""Approval gate for architecture specs."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from refactor_framework.config import AppConfig
from refactor_framework.models import SpecApproval
from refactor_framework.spec.generator import load_spec_json, save_spec

logger = logging.getLogger("refactor_framework.spec")


def record_approval(
    config: AppConfig,
    increment_id: str,
    approved_by: str,
    notes: str = "",
) -> SpecApproval:
    """Record human approval on an architecture spec.

    Loads the existing spec, attaches the approval, and re-saves.
    """
    spec = load_spec_json(config, increment_id)
    if spec is None:
        raise FileNotFoundError(
            f"No spec.json found for {increment_id}. Run 'spec' command first."
        )

    approval = SpecApproval(
        approved_by=approved_by,
        approved_at=datetime.now(timezone.utc).isoformat(),
        notes=notes,
        version=spec.approval.version + 1 if spec.approval else 1,
    )

    spec.approval = approval
    save_spec(config, increment_id, spec)

    logger.info("Spec approved by %s for %s", approved_by, increment_id)
    return approval


def check_approval(config: AppConfig, increment_id: str) -> bool:
    """Check whether the spec for an increment has been approved."""
    spec = load_spec_json(config, increment_id)
    if spec is None:
        return False
    return spec.approval is not None


def has_spec(config: AppConfig, increment_id: str) -> bool:
    """Check whether a spec exists (generated or approved)."""
    json_path = Path(config.project.increments_dir) / increment_id / "spec.json"
    return json_path.exists()
