"""Tests for methodology document generation."""

from __future__ import annotations

from refactor_framework.methodology.generator import (
    build_decision_log,
    build_metrics_summary,
    build_spec_vs_actual,
    generate_methodology,
)
from refactor_framework.models import (
    ArchitectureSpec,
    ConstructMapping,
    EfficiencyMetrics,
    IncrementPlan,
    IncrementRecord,
    IncrementSnapshot,
    ModuleDecision,
    RiskItem,
    TokenUsage,
)


def _make_spec_and_record():
    spec = ArchitectureSpec(
        increment_id="20260327T000000",
        module_decisions=[
            ModuleDecision(
                source_construct="PROC_SORT",
                source_file="old.sas",
                target_approach="Polars sort",
                chosen_alternative="B: Idiomatic",
                rationale="Better perf",
            ),
        ],
        risks=[RiskItem(description="Test risk", severity="low")],
        scaling_considerations=[],
    )

    record = IncrementRecord(
        increment_id="20260327T000000",
        status="reported",
        plan=IncrementPlan(
            increment_id="20260327T000000",
            description="Test",
            construct_mappings=[
                ConstructMapping(
                    source_construct="PROC_SORT",
                    source_file="old.sas",
                    target_construct="sort_func",
                    target_file="new.py",
                    status="COMPLETE",
                ),
            ],
            acceptance_criteria=["Tests pass"],
        ),
        before=IncrementSnapshot(phase="before", total_loc=100),
        after=IncrementSnapshot(phase="after", total_loc=80),
        token_usage=TokenUsage(total_tokens=5000, cost_estimate_usd=0.05),
        efficiency=EfficiencyMetrics(loc_delta=-20),
    )
    return spec, record


class TestBuildSpecVsActual:
    def test_matches_construct(self):
        spec, record = _make_spec_and_record()
        results = build_spec_vs_actual(spec, record)
        assert len(results) == 1
        assert results[0]["source_construct"] == "PROC_SORT"
        assert results[0]["actual_status"] == "COMPLETE"

    def test_unmatched_construct_shows_not_implemented(self):
        spec, record = _make_spec_and_record()
        spec.module_decisions.append(
            ModuleDecision(source_construct="MISSING", source_file="x.sas")
        )
        results = build_spec_vs_actual(spec, record)
        missing = [r for r in results if r["source_construct"] == "MISSING"]
        assert missing[0]["actual_target"] == "NOT IMPLEMENTED"


class TestBuildDecisionLog:
    def test_logs_each_decision(self):
        spec, record = _make_spec_and_record()
        log = build_decision_log(spec, record)
        assert len(log) >= 1
        assert log[0]["chosen_option"] == "B: Idiomatic"


class TestBuildMetricsSummary:
    def test_computes_summary(self):
        _, record = _make_spec_and_record()
        summary = build_metrics_summary(record)
        assert summary["loc_before"] == 100
        assert summary["loc_after"] == 80
        assert summary["loc_delta"] == -20
        assert summary["tokens_used"] == 5000


class TestGenerateMethodology:
    def test_produces_full_methodology(self):
        spec, record = _make_spec_and_record()
        meth = generate_methodology(record, spec)
        assert meth.increment_id == "20260327T000000"
        assert len(meth.spec_vs_actual) >= 1
        assert len(meth.decision_log) >= 1
        assert meth.metrics_summary["loc_delta"] == -20
