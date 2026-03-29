"""Tests for test suite runner."""

from __future__ import annotations

from pathlib import Path

import pytest

from refactor_framework.config import AppConfig, ProjectConfig, TestConfig
from refactor_framework.test.runner import _parse_pytest_output, run_tests


class TestParsePytestOutput:
    def test_parses_all_passed(self):
        output = "========================= 5 passed in 0.05s ========================="
        p, f, e, s = _parse_pytest_output(output)
        assert (p, f, e, s) == (5, 0, 0, 0)

    def test_parses_mixed_results(self):
        output = "============= 3 passed, 2 failed, 1 error in 1.23s ============="
        p, f, e, s = _parse_pytest_output(output)
        assert (p, f, e, s) == (3, 2, 1, 0)

    def test_parses_with_skipped(self):
        output = "========= 10 passed, 1 skipped in 0.50s ========="
        p, f, e, s = _parse_pytest_output(output)
        assert (p, f, e, s) == (10, 0, 0, 1)

    def test_no_summary_returns_zeros(self):
        output = "some random output without pytest summary"
        p, f, e, s = _parse_pytest_output(output)
        assert (p, f, e, s) == (0, 0, 0, 0)


class TestRunTests:
    def _make_config(self, tmp_path: Path) -> AppConfig:
        inc_dir = tmp_path / "increments"
        inc_dir.mkdir()
        return AppConfig(
            project=ProjectConfig(
                target_repo=str(tmp_path),
                increments_dir=str(inc_dir),
            ),
            test=TestConfig(
                default_command="echo '5 passed in 0.01s'",
                timeout_seconds=30,
            ),
        )

    def test_runs_command_and_records(self, tmp_path: Path):
        config = self._make_config(tmp_path)
        inc_id = "20260326T100000"
        (Path(config.project.increments_dir) / inc_id).mkdir()

        result = run_tests(config, inc_id, "before", command="echo '3 passed in 0.01s'")
        assert result.duration_seconds >= 0
        assert result.command == "echo '3 passed in 0.01s'"

    def test_invalid_phase_raises(self, tmp_path: Path):
        config = self._make_config(tmp_path)
        with pytest.raises(ValueError, match="Phase must be"):
            run_tests(config, "test", "middle")

    def test_persists_result_file(self, tmp_path: Path):
        config = self._make_config(tmp_path)
        inc_id = "20260326T100000"
        (Path(config.project.increments_dir) / inc_id).mkdir()

        run_tests(config, inc_id, "before", command="echo done")

        result_file = Path(config.project.increments_dir) / inc_id / "test_before.json"
        assert result_file.exists()
