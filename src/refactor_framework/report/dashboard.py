"""Aggregate metrics computation across all increments."""

from __future__ import annotations

from refactor_framework.models import IncrementRecord


def compute_dashboard_data(records: list[IncrementRecord]) -> dict:
    """Compute aggregate metrics for the dashboard.

    Returns a dict with summary statistics, per-increment data, and efficiency metrics.
    """
    total_increments = len(records)
    total_loc_delta = 0
    total_cc_delta = 0.0
    total_mi_delta = 0.0
    total_tokens = 0
    total_cost = 0.0
    total_time_hours = 0.0
    total_files_changed = 0

    increment_rows = []

    for r in records:
        loc_delta = r.efficiency.loc_delta
        cc_delta = r.efficiency.complexity_delta
        mi_delta = r.efficiency.maintainability_delta
        tokens = r.token_usage.total_tokens
        cost = r.token_usage.cost_estimate_usd
        hours = r.time_record.duration_seconds / 3600.0
        files = len(r.plan.target_files)

        total_loc_delta += loc_delta
        total_cc_delta += cc_delta
        total_mi_delta += mi_delta
        total_tokens += tokens
        total_cost += cost
        total_time_hours += hours
        total_files_changed += files

        increment_rows.append({
            "increment_id": r.increment_id,
            "date": r.plan.created_at[:10] if r.plan.created_at else "",
            "description": r.plan.description,
            "status": r.status,
            "files": files,
            "loc_delta": loc_delta,
            "cc_delta": round(cc_delta, 2),
            "mi_delta": round(mi_delta, 2),
            "tokens": tokens,
            "cost": round(cost, 4),
            "duration_hours": round(hours, 2),
        })

    # Efficiency ratios
    lines_per_1k_tokens = (
        abs(total_loc_delta) / (total_tokens / 1000.0) if total_tokens > 0 else 0.0
    )
    cc_per_hour = abs(total_cc_delta) / total_time_hours if total_time_hours > 0 else 0.0
    avg_cost_per_increment = total_cost / total_increments if total_increments > 0 else 0.0

    return {
        "summary": {
            "total_increments": total_increments,
            "total_loc_delta": total_loc_delta,
            "total_cc_delta": round(total_cc_delta, 2),
            "total_mi_delta": round(total_mi_delta, 2),
            "total_tokens": total_tokens,
            "total_cost": round(total_cost, 4),
            "total_time_hours": round(total_time_hours, 2),
            "total_files_changed": total_files_changed,
        },
        "efficiency": {
            "lines_per_1k_tokens": round(lines_per_1k_tokens, 2),
            "cc_per_hour": round(cc_per_hour, 2),
            "avg_cost_per_increment": round(avg_cost_per_increment, 4),
        },
        "increments": increment_rows,
    }
