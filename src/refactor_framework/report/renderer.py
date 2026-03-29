"""Jinja2 HTML report rendering."""

from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from refactor_framework.models import IncrementPlan, IncrementRecord
from refactor_framework.report.dashboard import compute_dashboard_data
from refactor_framework.utils.paths import ensure_dir

logger = logging.getLogger("refactor_framework.report")

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def _get_env(template_dir: str | None = None) -> Environment:
    """Create Jinja2 environment with the templates directory."""
    tpl_dir = Path(template_dir) if template_dir else _TEMPLATES_DIR
    return Environment(
        loader=FileSystemLoader(str(tpl_dir)),
        autoescape=True,
    )


def render_increment_report(
    record: IncrementRecord,
    diffs: list[dict],
    output_path: Path,
    template_dir: str | None = None,
    plan: IncrementPlan | None = None,
    increment_dir: Path | None = None,
) -> Path:
    """Render per-increment HTML report.

    For cross-language mode, pass the plan with construct_mappings and
    the increment_dir for code snippet extraction.
    """
    env = _get_env(template_dir)
    env.autoescape = False

    # Detect cross-language mode
    effective_plan = plan or record.plan
    is_cross = effective_plan.migration.mode == "cross-language"

    if is_cross and effective_plan.construct_mappings:
        return _render_migration_report(
            record, effective_plan, output_path, env, increment_dir,
        )

    return _render_same_language_report(record, diffs, output_path, env)


def _render_same_language_report(
    record: IncrementRecord,
    diffs: list[dict],
    output_path: Path,
    env: Environment,
) -> Path:
    """Render the standard same-language diff-based report."""
    template = env.get_template("increment_report.html")

    before_metrics = {f.file_path: f for f in (record.before.files if record.before else [])}
    after_metrics = {f.file_path: f for f in (record.after.files if record.after else [])}

    file_comparisons = []
    all_files = sorted(set(list(before_metrics.keys()) + list(after_metrics.keys())))
    for fp in all_files:
        bm = before_metrics.get(fp)
        am = after_metrics.get(fp)
        file_comparisons.append({
            "file_path": fp,
            "loc_before": bm.loc_total if bm else 0,
            "loc_after": am.loc_total if am else 0,
            "loc_delta": (am.loc_total if am else 0) - (bm.loc_total if bm else 0),
            "cc_before": round(bm.cyclomatic_complexity_avg, 2) if bm else 0,
            "cc_after": round(am.cyclomatic_complexity_avg, 2) if am else 0,
            "cc_delta": round(
                (am.cyclomatic_complexity_avg if am else 0)
                - (bm.cyclomatic_complexity_avg if bm else 0),
                2,
            ),
            "mi_before": round(bm.maintainability_index, 2) if bm else 0,
            "mi_after": round(am.maintainability_index, 2) if am else 0,
            "mi_delta": round(
                (am.maintainability_index if am else 0)
                - (bm.maintainability_index if bm else 0),
                2,
            ),
        })

    context = {
        "record": asdict(record),
        "diffs": diffs,
        "file_comparisons": file_comparisons,
        "files_changed": sum(1 for d in diffs if d["changed"]),
        "total_added": sum(d["added"] for d in diffs),
        "total_removed": sum(d["removed"] for d in diffs),
    }

    html = template.render(**context)
    ensure_dir(output_path.parent)
    output_path.write_text(html, encoding="utf-8")
    logger.info("Increment report written to %s", output_path)
    return output_path


def _render_migration_report(
    record: IncrementRecord,
    plan: IncrementPlan,
    output_path: Path,
    env: Environment,
    increment_dir: Path | None = None,
) -> Path:
    """Render the cross-language migration report."""
    from refactor_framework.report.migration import (
        generate_annotated_panels,
        generate_construct_table,
        generate_coverage_summary,
        generate_file_mapping_data,
        generate_language_metrics,
        generate_migration_overview,
    )

    template = env.get_template("migration_report.html")

    source_dir = increment_dir / "before" if increment_dir else Path(".")
    target_dir = increment_dir / "after" if increment_dir else Path(".")

    context = {
        "record": asdict(record),
        "overview": generate_migration_overview(record),
        "file_mapping": generate_file_mapping_data(record),
        "construct_table": generate_construct_table(plan.construct_mappings),
        "coverage": generate_coverage_summary(plan.construct_mappings),
        "annotated_panels": generate_annotated_panels(
            plan.construct_mappings, source_dir, target_dir,
        ),
        "lang_metrics": generate_language_metrics(record),
    }

    html = template.render(**context)
    ensure_dir(output_path.parent)
    output_path.write_text(html, encoding="utf-8")
    logger.info("Migration report written to %s", output_path)
    return output_path


def render_dashboard(
    records: list[IncrementRecord],
    output_path: Path,
    template_dir: str | None = None,
) -> Path:
    """Render aggregate dashboard HTML report."""
    env = _get_env(template_dir)
    env.autoescape = False
    template = env.get_template("dashboard.html")

    data = compute_dashboard_data(records)
    html = template.render(**data)

    ensure_dir(output_path.parent)
    output_path.write_text(html, encoding="utf-8")
    logger.info("Dashboard written to %s", output_path)
    return output_path
