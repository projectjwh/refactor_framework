"""Tests for migration report data generators."""

from __future__ import annotations

from refactor_framework.models import (
    ConstructMapping,
    FileMetrics,
    IncrementPlan,
    IncrementRecord,
    IncrementSnapshot,
    MigrationConfig,
)
from refactor_framework.report.migration import (
    generate_construct_table,
    generate_coverage_summary,
    generate_file_mapping_data,
    generate_language_metrics,
    generate_migration_overview,
)


def _make_record() -> IncrementRecord:
    return IncrementRecord(
        increment_id="20260327T000000",
        plan=IncrementPlan(
            source_files=["old.sas"],
            target_files=["new.py"],
            description="Test migration",
            construct_mappings=[
                ConstructMapping(
                    source_file="old.sas", source_construct="PROC_X",
                    target_file="new.py", target_construct="func_x",
                    status="COMPLETE", mapping_type="refactored",
                    description="Refactored",
                ),
            ],
            migration=MigrationConfig(
                mode="cross-language",
                source_language="SAS", target_language="Python",
            ),
        ),
        before=IncrementSnapshot(
            phase="before",
            files=[FileMetrics(file_path="old.sas", language="SAS", loc_total=100)],
            total_loc=100,
        ),
        after=IncrementSnapshot(
            phase="after",
            files=[FileMetrics(file_path="new.py", language="Python", loc_total=75)],
            total_loc=75,
        ),
    )


class TestMigrationOverview:
    def test_basic_overview(self):
        record = _make_record()
        ov = generate_migration_overview(record)
        assert ov["source_language"] == "SAS"
        assert ov["target_language"] == "Python"
        assert ov["source_total_loc"] == 100
        assert ov["target_total_loc"] == 75


class TestFileMappingData:
    def test_maps_source_to_target(self):
        record = _make_record()
        fms = generate_file_mapping_data(record)
        assert len(fms) >= 1
        assert fms[0]["source_file"] == "old.sas"
        assert "new.py" in fms[0]["target_files"]


class TestConstructTable:
    def test_builds_rows(self):
        mappings = _make_record().plan.construct_mappings
        rows = generate_construct_table(mappings)
        assert len(rows) == 1
        assert rows[0]["source_construct"] == "PROC_X"
        assert rows[0]["status"] == "COMPLETE"


class TestCoverageSummary:
    def test_computes_coverage(self):
        mappings = _make_record().plan.construct_mappings
        cov = generate_coverage_summary(mappings)
        assert cov["total"] == 1
        assert cov["complete"] == 1
        assert cov["pct_complete"] == 100.0


class TestLanguageMetrics:
    def test_splits_by_language(self):
        record = _make_record()
        lm = generate_language_metrics(record)
        assert len(lm["source"]) == 1
        assert lm["source"][0]["language"] == "SAS"
        assert len(lm["target"]) == 1
        assert lm["target"][0]["language"] == "Python"
