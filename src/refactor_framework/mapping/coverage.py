"""Cross-increment source coverage and burndown analytics.

Answers: "What % of the source codebase has been migrated across all increments?"
and "When will we finish at the current velocity?"
"""

from __future__ import annotations

import logging

from refactor_framework.models import ConstructMapping, IncrementRecord

logger = logging.getLogger("refactor_framework.mapping")


def compute_source_coverage(records: list[IncrementRecord]) -> dict:
    """Compute coverage across ALL increments.

    Returns:
        source_files: list of {file, total_constructs, complete, partial, todo, pct}
        totals: {constructs, complete, partial, todo, removed, pct_complete}
        unmapped_constructs: list of {source_file, construct, increment_id}
    """
    # Collect all mappings across all increments
    all_mappings: list[tuple[str, ConstructMapping]] = []
    for r in records:
        for m in r.plan.construct_mappings:
            all_mappings.append((r.increment_id, m))

    if not all_mappings:
        return {
            "source_files": [],
            "totals": _empty_totals(),
            "unmapped_constructs": [],
        }

    # Group by source file
    by_file: dict[str, list[tuple[str, ConstructMapping]]] = {}
    for inc_id, m in all_mappings:
        key = m.source_file or "(unmapped)"
        by_file.setdefault(key, []).append((inc_id, m))

    source_files = []
    total_complete = total_partial = total_todo = total_removed = 0
    unmapped = []

    for sf in sorted(by_file.keys()):
        items = by_file[sf]
        counts = {"COMPLETE": 0, "PARTIAL": 0, "TODO": 0, "REMOVED": 0}
        for inc_id, m in items:
            counts[m.status] = counts.get(m.status, 0) + 1
            if m.status == "TODO":
                unmapped.append({
                    "source_file": sf,
                    "construct": m.source_construct,
                    "increment_id": inc_id,
                })

        total = sum(counts.values())
        actionable = total - counts["REMOVED"]
        pct = round(counts["COMPLETE"] / actionable * 100, 1) if actionable > 0 else 0.0

        source_files.append({
            "file": sf,
            "total_constructs": total,
            "complete": counts["COMPLETE"],
            "partial": counts["PARTIAL"],
            "todo": counts["TODO"],
            "removed": counts["REMOVED"],
            "pct": pct,
        })

        total_complete += counts["COMPLETE"]
        total_partial += counts["PARTIAL"]
        total_todo += counts["TODO"]
        total_removed += counts["REMOVED"]

    grand_total = total_complete + total_partial + total_todo + total_removed
    actionable = grand_total - total_removed
    pct = round(total_complete / actionable * 100, 1) if actionable > 0 else 0.0

    return {
        "source_files": source_files,
        "totals": {
            "constructs": grand_total,
            "complete": total_complete,
            "partial": total_partial,
            "todo": total_todo,
            "removed": total_removed,
            "pct_complete": pct,
        },
        "unmapped_constructs": unmapped,
    }


def compute_burndown(records: list[IncrementRecord]) -> dict:
    """Compute velocity and burndown metrics across increments.

    Returns:
        increments_timeline: list of per-increment cumulative data
        velocity: {avg_loc_per_increment, avg_cost_per_increment, avg_constructs_per_increment}
        burndown: {remaining_todo, estimated_increments_left, cost_per_loc}
    """
    if not records:
        return {
            "increments_timeline": [],
            "velocity": _empty_velocity(),
            "burndown": _empty_burndown(),
        }

    timeline = []
    cum_loc_source = 0
    cum_loc_target = 0
    cum_tokens = 0
    cum_cost = 0.0
    cum_constructs_done = 0
    cum_time_hours = 0.0
    costs_per_loc = []

    for i, r in enumerate(records):
        src_loc = r.before.total_loc if r.before else 0
        tgt_loc = r.after.total_loc if r.after else 0
        tokens = r.token_usage.total_tokens
        cost = r.token_usage.cost_estimate_usd
        hours = r.time_record.duration_seconds / 3600.0
        n_complete = sum(1 for m in r.plan.construct_mappings if m.status == "COMPLETE")

        cum_loc_source += src_loc
        cum_loc_target += tgt_loc
        cum_tokens += tokens
        cum_cost += cost
        cum_constructs_done += n_complete
        cum_time_hours += hours

        if tgt_loc > 0 and tokens > 0:
            costs_per_loc.append(cost / tgt_loc)

        timeline.append({
            "seq": i + 1,
            "increment_id": r.increment_id,
            "date": r.plan.created_at[:10] if r.plan.created_at else "",
            "source_loc": src_loc,
            "target_loc": tgt_loc,
            "tokens": tokens,
            "cost": round(cost, 4),
            "hours": round(hours, 2),
            "constructs_done": n_complete,
            "cum_source_loc": cum_loc_source,
            "cum_target_loc": cum_loc_target,
            "cum_tokens": cum_tokens,
            "cum_cost": round(cum_cost, 4),
            "cum_constructs": cum_constructs_done,
            "cum_hours": round(cum_time_hours, 2),
        })

    n = len(records)
    avg_loc = cum_loc_target / n if n > 0 else 0
    avg_cost = cum_cost / n if n > 0 else 0
    avg_constructs = cum_constructs_done / n if n > 0 else 0
    avg_cost_per_loc = sum(costs_per_loc) / len(costs_per_loc) if costs_per_loc else 0

    # Estimate remaining work
    coverage = compute_source_coverage(records)
    remaining_todo = coverage["totals"]["todo"] + coverage["totals"]["partial"]
    est_increments = (
        round(remaining_todo / avg_constructs, 1) if avg_constructs > 0 else 0
    )
    est_cost = round(est_increments * avg_cost, 2) if est_increments > 0 else 0

    return {
        "increments_timeline": timeline,
        "velocity": {
            "avg_loc_per_increment": round(avg_loc, 0),
            "avg_cost_per_increment": round(avg_cost, 4),
            "avg_constructs_per_increment": round(avg_constructs, 1),
            "avg_cost_per_loc": round(avg_cost_per_loc, 6),
            "avg_hours_per_increment": round(cum_time_hours / n, 2) if n > 0 else 0,
        },
        "burndown": {
            "remaining_todo": remaining_todo,
            "estimated_increments_left": est_increments,
            "estimated_cost_remaining": est_cost,
            "total_increments_completed": n,
        },
    }


def _empty_totals() -> dict:
    return {
        "constructs": 0, "complete": 0, "partial": 0,
        "todo": 0, "removed": 0, "pct_complete": 0.0,
    }


def _empty_velocity() -> dict:
    return {
        "avg_loc_per_increment": 0, "avg_cost_per_increment": 0,
        "avg_constructs_per_increment": 0, "avg_cost_per_loc": 0,
        "avg_hours_per_increment": 0,
    }


def _empty_burndown() -> dict:
    return {
        "remaining_todo": 0, "estimated_increments_left": 0,
        "estimated_cost_remaining": 0, "total_increments_completed": 0,
    }
