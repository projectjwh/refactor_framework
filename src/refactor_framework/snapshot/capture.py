"""File snapshot capture with metrics computation."""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from refactor_framework.config import AppConfig
from refactor_framework.models import IncrementSnapshot
from refactor_framework.plan.planner import load_plan
from refactor_framework.snapshot.metrics import compute_file_metrics
from refactor_framework.utils.paths import ensure_dir

logger = logging.getLogger("refactor_framework.snapshot")


def capture_snapshot(config: AppConfig, increment_id: str, phase: str) -> IncrementSnapshot:
    """Capture file snapshot and compute metrics.

    Parameters
    ----------
    config : AppConfig
    increment_id : str
    phase : str
        "before" or "after"

    Returns
    -------
    IncrementSnapshot with computed metrics for all plan target files.
    """
    if phase not in ("before", "after"):
        raise ValueError(f"Phase must be 'before' or 'after', got '{phase}'")

    inc_dir = Path(config.project.increments_dir) / increment_id
    plan = load_plan(config.project.increments_dir, increment_id)

    # Determine repo and file list based on migration mode
    is_cross = plan.migration.mode == "cross-language"
    if is_cross and phase == "before" and plan.source_files:
        repo = Path(plan.migration.source_repo)
        file_list = plan.source_files
    else:
        repo = Path(config.project.target_repo)
        file_list = plan.target_files

    snapshot_dir = ensure_dir(inc_dir / phase)
    file_metrics_list = []

    for rel_path in file_list:
        src = repo / rel_path
        dst = snapshot_dir / rel_path
        ensure_dir(dst.parent)

        if src.exists():
            shutil.copy2(src, dst)
            fm = compute_file_metrics(dst, config.snapshot.metrics_backend)
            fm.file_path = rel_path
            file_metrics_list.append(fm)
        else:
            logger.warning("File not found (skipping): %s", src)

    # Compute aggregates
    total_loc = sum(fm.loc_total for fm in file_metrics_list)
    avg_cc = (
        sum(fm.cyclomatic_complexity_avg for fm in file_metrics_list) / len(file_metrics_list)
        if file_metrics_list
        else 0.0
    )
    avg_mi = (
        sum(fm.maintainability_index for fm in file_metrics_list) / len(file_metrics_list)
        if file_metrics_list
        else 0.0
    )

    snapshot = IncrementSnapshot(
        phase=phase,
        timestamp=datetime.now(timezone.utc).isoformat(),
        files=file_metrics_list,
        total_loc=total_loc,
        avg_complexity=avg_cc,
        avg_maintainability=avg_mi,
    )

    # Persist metrics JSON
    metrics_file = inc_dir / f"{phase}_metrics.json"
    metrics_file.write_text(
        json.dumps(asdict(snapshot), indent=2, default=str),
        encoding="utf-8",
    )

    logger.info(
        "Captured %s snapshot for %s: %d files, %d LOC",
        phase, increment_id, len(file_metrics_list), total_loc,
    )
    return snapshot
