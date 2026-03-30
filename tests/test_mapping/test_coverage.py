"""Tests for source coverage and burndown analytics."""

from __future__ import annotations

from refactor_framework.mapping.coverage import compute_burndown, compute_source_coverage
from refactor_framework.models import (
    ConstructMapping,
    EfficiencyMetrics,
    IncrementPlan,
    IncrementRecord,
    IncrementSnapshot,
    TimeRecord,
    TokenUsage,
)


def _make_record(inc_id: str, mappings: list[ConstructMapping]) -> IncrementRecord:
    return IncrementRecord(
        increment_id=inc_id,
        plan=IncrementPlan(
            increment_id=inc_id,
            construct_mappings=mappings,
            created_at="2026-03-27T00:00:00",
        ),
        before=IncrementSnapshot(phase="before", total_loc=100),
        after=IncrementSnapshot(phase="after", total_loc=80),
        token_usage=TokenUsage(total_tokens=5000, cost_estimate_usd=0.05),
        time_record=TimeRecord(duration_seconds=60.0),
        efficiency=EfficiencyMetrics(loc_delta=-20),
    )


class TestComputeSourceCoverage:
    def test_computes_per_file(self):
        records = [_make_record("inc1", [
            ConstructMapping(source_file="a.sas", source_construct="X", status="COMPLETE"),
            ConstructMapping(source_file="a.sas", source_construct="Y", status="TODO"),
            ConstructMapping(source_file="b.sas", source_construct="Z", status="COMPLETE"),
        ])]
        cov = compute_source_coverage(records)
        assert cov["totals"]["constructs"] == 3
        assert cov["totals"]["complete"] == 2
        assert cov["totals"]["todo"] == 1
        assert len(cov["source_files"]) == 2

    def test_cross_increment_coverage(self):
        records = [
            _make_record("inc1", [
                ConstructMapping(source_file="a.sas", source_construct="X", status="COMPLETE"),
            ]),
            _make_record("inc2", [
                ConstructMapping(source_file="a.sas", source_construct="Y", status="COMPLETE"),
            ]),
        ]
        cov = compute_source_coverage(records)
        assert cov["totals"]["constructs"] == 2
        assert cov["totals"]["complete"] == 2

    def test_empty_records(self):
        cov = compute_source_coverage([])
        assert cov["totals"]["constructs"] == 0

    def test_unmapped_listed(self):
        records = [_make_record("inc1", [
            ConstructMapping(source_file="a.sas", source_construct="TODO_ONE", status="TODO"),
        ])]
        cov = compute_source_coverage(records)
        assert len(cov["unmapped_constructs"]) == 1
        assert cov["unmapped_constructs"][0]["construct"] == "TODO_ONE"


class TestComputeBurndown:
    def test_computes_velocity(self):
        records = [
            _make_record("inc1", [
                ConstructMapping(status="COMPLETE"),
                ConstructMapping(status="COMPLETE"),
            ]),
        ]
        burn = compute_burndown(records)
        assert burn["velocity"]["avg_loc_per_increment"] > 0
        assert burn["velocity"]["avg_cost_per_increment"] > 0
        assert burn["burndown"]["total_increments_completed"] == 1

    def test_timeline_ordered(self):
        records = [
            _make_record("inc1", [ConstructMapping(status="COMPLETE")]),
            _make_record("inc2", [ConstructMapping(status="COMPLETE")]),
        ]
        burn = compute_burndown(records)
        assert len(burn["increments_timeline"]) == 2
        assert burn["increments_timeline"][0]["seq"] == 1
        assert burn["increments_timeline"][1]["seq"] == 2

    def test_empty_records(self):
        burn = compute_burndown([])
        assert burn["burndown"]["total_increments_completed"] == 0
