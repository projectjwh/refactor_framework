"""Tests for core data models."""

from __future__ import annotations

import json
from dataclasses import asdict

from refactor_framework.models import (
    EfficiencyMetrics,
    FileMetrics,
    IncrementPlan,
    IncrementRecord,
    IncrementSnapshot,
    IncrementStatus,
    TimeRecord,
    TokenUsage,
)


class TestIncrementStatus:
    def test_values(self):
        assert IncrementStatus.PLANNED.value == "planned"
        assert IncrementStatus.ARCHIVED.value == "archived"

    def test_all_statuses_exist(self):
        expected = {
            "planned", "spec_generated", "spec_approved",
            "snapshot_before", "executing",
            "snapshot_after", "tested", "reported",
            "methodology", "archived",
        }
        assert {s.value for s in IncrementStatus} == expected


class TestFileMetrics:
    def test_defaults(self):
        fm = FileMetrics()
        assert fm.file_path == ""
        assert fm.loc_total == 0
        assert fm.cyclomatic_complexity_avg == 0.0

    def test_construction(self):
        fm = FileMetrics(
            file_path="src/main.py",
            loc_total=100,
            loc_code=80,
            cyclomatic_complexity_avg=5.2,
            maintainability_index=72.0,
        )
        assert fm.file_path == "src/main.py"
        assert fm.loc_code == 80


class TestIncrementRecord:
    def test_defaults(self):
        record = IncrementRecord()
        assert record.status == "planned"
        assert record.before is None
        assert record.after is None
        assert record.token_usage.total_tokens == 0

    def test_full_construction(self):
        record = IncrementRecord(
            increment_id="20260326T143022",
            status="reported",
            plan=IncrementPlan(
                increment_id="20260326T143022",
                description="Refactor utils",
                target_files=["utils.py"],
            ),
            before=IncrementSnapshot(phase="before", total_loc=500),
            after=IncrementSnapshot(phase="after", total_loc=420),
            token_usage=TokenUsage(input_tokens=1500, output_tokens=800, total_tokens=2300),
            time_record=TimeRecord(duration_seconds=3600.0),
            efficiency=EfficiencyMetrics(loc_delta=-80, complexity_delta=-3.2),
        )
        assert record.increment_id == "20260326T143022"
        assert record.before.total_loc == 500
        assert record.after.total_loc == 420
        assert record.efficiency.loc_delta == -80

    def test_serialization_roundtrip(self):
        record = IncrementRecord(
            increment_id="20260326T143022",
            token_usage=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150),
        )
        data = asdict(record)
        json_str = json.dumps(data)
        restored = json.loads(json_str)
        assert restored["increment_id"] == "20260326T143022"
        assert restored["token_usage"]["total_tokens"] == 150
