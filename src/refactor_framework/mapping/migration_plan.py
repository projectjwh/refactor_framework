"""Master migration plan — full decomposition with dependency DAG.

Defines the overall migration roadmap: all planned increments, their
dependencies, and ordering. Used to answer "what's the full scope?"
and "what order should we execute?"
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

logger = logging.getLogger("refactor_framework.mapping")


def load_migration_plan(yaml_path: Path) -> dict:
    """Load a master migration plan from YAML.

    Expected schema:
        name: "SAS to Python Migration"
        source_language: SAS
        target_language: Python
        source_repo: /path/to/sas
        target_repo: /path/to/python
        increments:
          - id: enrollment-config
            description: "Migrate config macros"
            source_files: ["00_config.sas"]
            target_files: ["config.py"]
            priority: 1
            depends_on: []
            status: COMPLETE
            increment_id: "20260327T011111"  # linked after creation
          - id: enrollment-process
            description: "Migrate processing macro"
            source_files: ["02_enroll_process.sas"]
            target_files: ["enroll_process.py"]
            priority: 2
            depends_on: [enrollment-config]
            status: TODO
    """
    if not yaml_path.exists():
        raise FileNotFoundError(f"Migration plan not found: {yaml_path}")

    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    if not data or "increments" not in data:
        raise ValueError("Migration plan must contain an 'increments' key")

    return data


def save_migration_plan(data: dict, yaml_path: Path) -> None:
    """Save a master migration plan to YAML."""
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    yaml_path.write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def compute_dag_order(plan: dict) -> list[str]:
    """Topological sort of increments by dependency. Returns ordered list of IDs."""
    increments = {inc["id"]: inc for inc in plan.get("increments", [])}
    visited = set()
    order = []

    def _visit(inc_id: str) -> None:
        if inc_id in visited:
            return
        visited.add(inc_id)
        inc = increments.get(inc_id, {})
        for dep in inc.get("depends_on", []):
            _visit(dep)
        order.append(inc_id)

    for inc_id in increments:
        _visit(inc_id)

    return order


def compute_plan_status(plan: dict) -> dict:
    """Compute summary status of the migration plan.

    Returns: total, complete, in_progress, todo, blocked, pct_complete.
    """
    increments = plan.get("increments", [])
    total = len(increments)
    complete = sum(1 for i in increments if i.get("status") == "COMPLETE")
    in_progress = sum(1 for i in increments if i.get("status") == "IN_PROGRESS")
    todo = sum(1 for i in increments if i.get("status") in ("TODO", None))

    # Blocked = TODO but has incomplete dependencies
    complete_ids = {i["id"] for i in increments if i.get("status") == "COMPLETE"}
    blocked = 0
    for i in increments:
        if i.get("status") in ("TODO", None):
            deps = i.get("depends_on", [])
            if deps and not all(d in complete_ids for d in deps):
                blocked += 1

    pct = round(complete / total * 100, 1) if total > 0 else 0.0

    return {
        "total": total,
        "complete": complete,
        "in_progress": in_progress,
        "todo": todo,
        "blocked": blocked,
        "ready": todo - blocked,
        "pct_complete": pct,
    }


def get_next_increments(plan: dict) -> list[dict]:
    """Return increments that are ready to start (TODO with all deps complete)."""
    increments = plan.get("increments", [])
    complete_ids = {i["id"] for i in increments if i.get("status") == "COMPLETE"}

    ready = []
    for i in increments:
        if i.get("status") not in ("TODO", None):
            continue
        deps = i.get("depends_on", [])
        if all(d in complete_ids for d in deps):
            ready.append(i)

    return sorted(ready, key=lambda x: x.get("priority", 999))


def render_dag_ascii(plan: dict) -> str:
    """Render a simple ASCII DAG of the migration plan."""
    increments = plan.get("increments", [])
    order = compute_dag_order(plan)
    inc_map = {i["id"]: i for i in increments}

    lines = []
    for inc_id in order:
        inc = inc_map.get(inc_id, {})
        status = inc.get("status", "TODO")
        marker = {"COMPLETE": "[x]", "IN_PROGRESS": "[~]", "TODO": "[ ]"}.get(status, "[ ]")
        deps = inc.get("depends_on", [])
        dep_str = f" (after: {', '.join(deps)})" if deps else ""
        desc = inc.get("description", "")[:50]
        lines.append(f"  {marker} {inc_id}: {desc}{dep_str}")

    return "\n".join(lines)
