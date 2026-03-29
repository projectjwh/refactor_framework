"""Methodology document generation — compares spec vs actual results."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from refactor_framework.models import (
    ArchitectureSpec,
    IncrementRecord,
    MethodologyRecord,
)

logger = logging.getLogger("refactor_framework.methodology")


def generate_methodology(
    record: IncrementRecord,
    spec: ArchitectureSpec,
) -> MethodologyRecord:
    """Generate a methodology document comparing spec to actual execution."""
    return MethodologyRecord(
        increment_id=record.increment_id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        spec_vs_actual=build_spec_vs_actual(spec, record),
        data_model_comparison=build_data_model_comparison(spec, record),
        decision_log=build_decision_log(spec, record),
        metrics_summary=build_metrics_summary(record),
    )


def build_spec_vs_actual(
    spec: ArchitectureSpec,
    record: IncrementRecord,
) -> list[dict]:
    """Compare each module decision from spec to what was actually built."""
    # Build lookup of actual construct mappings by source construct
    actual_by_source = {}
    for m in record.plan.construct_mappings:
        actual_by_source[m.source_construct] = m

    results = []
    for md in spec.module_decisions:
        actual = actual_by_source.get(md.source_construct)
        planned_target = md.target_approach
        actual_target = (
            f"{actual.target_construct} in {actual.target_file}"
            if actual else "NOT IMPLEMENTED"
        )
        actual_status = actual.status if actual else "TODO"
        deviated = actual is None or md.chosen_alternative == "" or actual_status != "COMPLETE"

        results.append({
            "source_construct": md.source_construct,
            "source_file": md.source_file,
            "planned_approach": planned_target,
            "chosen_alternative": md.chosen_alternative,
            "actual_target": actual_target,
            "actual_status": actual_status,
            "deviated": deviated,
            "notes": md.rationale,
        })

    return results


def build_data_model_comparison(
    spec: ArchitectureSpec,
    record: IncrementRecord,
) -> list[dict]:
    """Build side-by-side data model comparison from spec and actual metrics."""
    results = []

    # Use spec's planned data model changes
    for dm in spec.data_model_changes:
        results.append({
            "entity_name": dm.entity_name,
            "source_schema": dm.source_schema,
            "target_schema": dm.target_schema,
            "planned_changes": dm.changes,
            "grain_change": dm.grain_change,
        })

    # Enrich with actual file-level metrics
    before_files = {f.file_path: f for f in (record.before.files if record.before else [])}
    after_files = {f.file_path: f for f in (record.after.files if record.after else [])}

    if before_files or after_files:
        results.append({
            "entity_name": "File-Level LOC Comparison",
            "source_schema": {f: str(m.loc_total) for f, m in before_files.items()},
            "target_schema": {f: str(m.loc_total) for f, m in after_files.items()},
            "planned_changes": ["See module decisions above"],
            "grain_change": "",
        })

    return results


def build_decision_log(
    spec: ArchitectureSpec,
    record: IncrementRecord,
) -> list[dict]:
    """Build full decision log: planned decision + actual outcome."""
    actual_by_source = {}
    for m in record.plan.construct_mappings:
        actual_by_source[m.source_construct] = m

    log = []
    for md in spec.module_decisions:
        actual = actual_by_source.get(md.source_construct)
        actual_outcome = (
            f"Implemented as {actual.target_construct} ({actual.status})"
            if actual else "Not yet implemented"
        )
        match = actual is not None and actual.status == "COMPLETE"

        log.append({
            "decision": f"{md.source_construct} ({md.source_file})",
            "chosen_option": md.chosen_alternative,
            "planned_rationale": md.rationale,
            "actual_outcome": actual_outcome,
            "match": match,
        })

    # Add scaling decisions
    for sc in spec.scaling_considerations:
        log.append({
            "decision": f"Scaling: {sc.topic}",
            "chosen_option": sc.planned_approach,
            "planned_rationale": sc.notes or "",
            "actual_outcome": "[TO BE ASSESSED]",
            "match": False,
        })

    return log


def build_metrics_summary(record: IncrementRecord) -> dict:
    """Aggregate metrics for the methodology document."""
    from refactor_framework.mapping.loader import compute_coverage

    coverage = compute_coverage(record.plan.construct_mappings)

    return {
        "loc_before": record.before.total_loc if record.before else 0,
        "loc_after": record.after.total_loc if record.after else 0,
        "loc_delta": record.efficiency.loc_delta,
        "complexity_delta": record.efficiency.complexity_delta,
        "maintainability_delta": record.efficiency.maintainability_delta,
        "tokens_used": record.token_usage.total_tokens,
        "cost_usd": record.token_usage.cost_estimate_usd,
        "duration_seconds": record.time_record.duration_seconds,
        "test_before_passed": record.test_before.passed if record.test_before else 0,
        "test_after_passed": record.test_after.passed if record.test_after else 0,
        "coverage_pct": coverage["pct_complete"],
        "constructs_complete": coverage["complete"],
        "constructs_total": coverage["total"],
    }
