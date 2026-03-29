"""Tests for code metrics computation."""

from __future__ import annotations

from pathlib import Path

from refactor_framework.snapshot.metrics import compute_file_metrics


class TestComputeFileMetrics:
    def test_radon_backend_on_sample_before(self, fixtures_dir: Path):
        fm = compute_file_metrics(fixtures_dir / "sample_before.py", backend="radon")
        assert fm.loc_total > 0
        assert fm.loc_code > 0
        assert fm.cyclomatic_complexity_avg > 0
        assert fm.maintainability_index > 0
        assert fm.function_count >= 2  # process + get_summary

    def test_radon_backend_on_sample_after(self, fixtures_dir: Path):
        fm = compute_file_metrics(fixtures_dir / "sample_after.py", backend="radon")
        assert fm.loc_total > 0
        assert fm.loc_code > 0

    def test_after_has_lower_complexity_than_before(self, fixtures_dir: Path):
        before = compute_file_metrics(fixtures_dir / "sample_before.py", backend="radon")
        after = compute_file_metrics(fixtures_dir / "sample_after.py", backend="radon")
        # The refactored version should have lower avg complexity
        assert after.cyclomatic_complexity_avg < before.cyclomatic_complexity_avg

    def test_lizard_backend(self, fixtures_dir: Path):
        fm = compute_file_metrics(fixtures_dir / "sample_before.py", backend="lizard")
        assert fm.loc_total > 0
        assert fm.function_count > 0

    def test_both_backend(self, fixtures_dir: Path):
        fm = compute_file_metrics(fixtures_dir / "sample_before.py", backend="both")
        assert fm.loc_total > 0
        assert fm.cyclomatic_complexity_avg > 0

    def test_simple_file(self, tmp_path: Path):
        simple = tmp_path / "simple.py"
        simple.write_text("def hello():\n    return 'world'\n")
        fm = compute_file_metrics(simple, backend="radon")
        assert fm.loc_total >= 2
        assert fm.cyclomatic_complexity_avg >= 1.0
