"""Cross-language migration report data generators."""

from __future__ import annotations

import logging
from pathlib import Path

from refactor_framework.mapping.loader import compute_coverage
from refactor_framework.models import ConstructMapping, IncrementRecord

logger = logging.getLogger("refactor_framework.report")


def generate_migration_overview(record: IncrementRecord) -> dict:
    """Produce high-level migration overview data."""
    plan = record.plan
    before_files = record.before.files if record.before else []
    after_files = record.after.files if record.after else []

    return {
        "source_language": plan.migration.source_language,
        "target_language": plan.migration.target_language,
        "source_file_count": len(plan.source_files),
        "target_file_count": len(plan.target_files),
        "source_total_loc": sum(f.loc_total for f in before_files),
        "target_total_loc": sum(f.loc_total for f in after_files),
        "description": plan.description,
    }


def generate_file_mapping_data(record: IncrementRecord) -> list[dict]:
    """Build file-level mapping: which source files map to which target files.

    Derived from construct_mappings grouped by source_file.
    """
    plan = record.plan
    mappings = plan.construct_mappings

    # Build mapping from source → set of targets
    src_to_tgt: dict[str, set[str]] = {}
    for m in mappings:
        if m.source_file:
            src_to_tgt.setdefault(m.source_file, set())
            if m.target_file:
                src_to_tgt[m.source_file].add(m.target_file)

    # Build before/after LOC lookup
    before_loc = {f.file_path: f.loc_total for f in (record.before.files if record.before else [])}
    after_loc = {f.file_path: f.loc_total for f in (record.after.files if record.after else [])}

    rows = []
    for src in sorted(src_to_tgt.keys()):
        targets = sorted(src_to_tgt[src])
        rows.append({
            "source_file": src,
            "source_loc": before_loc.get(src, 0),
            "target_files": targets,
            "target_locs": [after_loc.get(t, 0) for t in targets],
            "target_total_loc": sum(after_loc.get(t, 0) for t in targets),
        })

    # Any target files not covered by a mapping
    mapped_targets = {t for targets in src_to_tgt.values() for t in targets}
    for tf in plan.target_files:
        if tf not in mapped_targets:
            rows.append({
                "source_file": "(new)",
                "source_loc": 0,
                "target_files": [tf],
                "target_locs": [after_loc.get(tf, 0)],
                "target_total_loc": after_loc.get(tf, 0),
            })

    return rows


def generate_construct_table(mappings: list[ConstructMapping]) -> list[dict]:
    """Build rows for the construct traceability matrix."""
    return [
        {
            "source_file": m.source_file,
            "source_construct": m.source_construct,
            "target_file": m.target_file,
            "target_construct": m.target_construct,
            "mapping_type": m.mapping_type,
            "status": m.status,
            "description": m.description,
        }
        for m in mappings
    ]


def generate_coverage_summary(mappings: list[ConstructMapping]) -> dict:
    """Compute coverage statistics for the migration."""
    return compute_coverage(mappings)


def generate_annotated_panels(
    mappings: list[ConstructMapping],
    source_dir: Path,
    target_dir: Path,
) -> list[dict]:
    """For each mapping, extract source and target code snippets.

    Returns list of dicts with: source_code, target_code, description,
    source_file, target_file, source_construct, target_construct,
    mapping_type, status.
    """
    panels = []
    for m in mappings:
        source_code = _extract_snippet(
            source_dir / m.source_file if m.source_file else None,
            m.source_line_start,
            m.source_line_end,
        )
        target_code = _extract_snippet(
            target_dir / m.target_file if m.target_file else None,
            m.target_line_start,
            m.target_line_end,
        )

        panels.append({
            "source_file": m.source_file,
            "source_construct": m.source_construct,
            "source_language": m.source_language,
            "target_file": m.target_file,
            "target_construct": m.target_construct,
            "target_language": m.target_language,
            "mapping_type": m.mapping_type,
            "status": m.status,
            "description": m.description,
            "source_code": source_code,
            "target_code": target_code,
            "has_line_ranges": m.source_line_start is not None or m.target_line_start is not None,
        })

    return panels


def generate_language_metrics(record: IncrementRecord) -> dict:
    """Split file metrics by language for the report."""
    source_metrics = []
    target_metrics = []

    if record.before:
        for f in record.before.files:
            source_metrics.append({
                "file_path": f.file_path,
                "language": f.language,
                "loc_total": f.loc_total,
                "loc_code": f.loc_code,
                "cc_avg": round(f.cyclomatic_complexity_avg, 2),
                "mi": round(f.maintainability_index, 2),
                "functions": f.function_count,
            })

    if record.after:
        for f in record.after.files:
            target_metrics.append({
                "file_path": f.file_path,
                "language": f.language,
                "loc_total": f.loc_total,
                "loc_code": f.loc_code,
                "cc_avg": round(f.cyclomatic_complexity_avg, 2),
                "mi": round(f.maintainability_index, 2),
                "functions": f.function_count,
            })

    return {"source": source_metrics, "target": target_metrics}


def _extract_snippet(
    file_path: Path | None,
    line_start: int | None,
    line_end: int | None,
) -> str:
    """Extract code snippet from a file, optionally by line range."""
    if file_path is None or not file_path.exists():
        return ""

    try:
        lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return ""

    if line_start is not None and line_end is not None:
        # Convert to 0-indexed, clamp to file bounds
        start = max(0, line_start - 1)
        end = min(len(lines), line_end)
        return "\n".join(lines[start:end])

    return "\n".join(lines)
