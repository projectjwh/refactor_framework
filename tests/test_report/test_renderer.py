"""Tests for HTML report rendering."""

from __future__ import annotations

from pathlib import Path

from refactor_framework.models import (
    EfficiencyMetrics,
    FileMetrics,
    IncrementPlan,
    IncrementRecord,
    IncrementSnapshot,
    TimeRecord,
    TokenUsage,
)
from refactor_framework.report.renderer import render_dashboard, render_increment_report


def _make_record() -> IncrementRecord:
    return IncrementRecord(
        increment_id="20260326T143022",
        status="reported",
        plan=IncrementPlan(
            increment_id="20260326T143022",
            description="Refactor legacy module",
            target_files=["legacy.py"],
            acceptance_criteria=["Tests pass", "CC reduced"],
            created_at="2026-03-26T14:30:22+00:00",
        ),
        before=IncrementSnapshot(
            phase="before",
            files=[FileMetrics(
                file_path="legacy.py", loc_total=100, loc_code=80,
                cyclomatic_complexity_avg=8.5, maintainability_index=45.0,
            )],
            total_loc=100, avg_complexity=8.5, avg_maintainability=45.0,
        ),
        after=IncrementSnapshot(
            phase="after",
            files=[FileMetrics(
                file_path="legacy.py", loc_total=75, loc_code=60,
                cyclomatic_complexity_avg=3.2, maintainability_index=72.0,
            )],
            total_loc=75, avg_complexity=3.2, avg_maintainability=72.0,
        ),
        token_usage=TokenUsage(
            input_tokens=5000, output_tokens=3000, total_tokens=8000,
            model="claude-sonnet-4-20250514", cost_estimate_usd=0.06,
        ),
        time_record=TimeRecord(
            start_time="2026-03-26T14:30:22", end_time="2026-03-26T15:30:22",
            duration_seconds=3600.0,
        ),
        efficiency=EfficiencyMetrics(
            loc_delta=-25, complexity_delta=-5.3, maintainability_delta=27.0,
            lines_changed_per_token=0.003125, complexity_delta_per_hour=5.3,
        ),
    )


class TestRenderIncrementReport:
    def test_generates_html_file(self, tmp_path: Path):
        record = _make_record()
        diffs = [{
            "rel_path": "legacy.py",
            "unified_diff": "--- a\n+++ b\n-old\n+new",
            "html_diff": "<p>diff</p>",
            "added": 5,
            "removed": 10,
            "changed": True,
        }]

        output = tmp_path / "report.html"
        result = render_increment_report(record, diffs, output)

        assert result == output
        assert output.exists()

        html = output.read_text()
        assert "20260326T143022" in html
        assert "Refactor legacy module" in html
        assert "legacy.py" in html
        assert "8,000" in html  # total tokens
        assert "-25" in html  # LOC delta

    def test_handles_no_diffs(self, tmp_path: Path):
        record = _make_record()
        output = tmp_path / "report.html"
        render_increment_report(record, [], output)
        assert output.exists()


class TestRenderDashboard:
    def test_generates_dashboard(self, tmp_path: Path):
        records = [_make_record()]
        output = tmp_path / "dashboard.html"

        result = render_dashboard(records, output)
        assert result == output
        assert output.exists()

        html = output.read_text()
        assert "Refactoring Dashboard" in html
        assert "1" in html  # total increments
        assert "8,000" in html  # tokens

    def test_handles_empty_records(self, tmp_path: Path):
        output = tmp_path / "dashboard.html"
        render_dashboard([], output)
        html = output.read_text()
        assert "0" in html  # 0 increments
