"""Tests for file snapshot capture."""

from __future__ import annotations

from pathlib import Path

import pytest

from refactor_framework.config import AppConfig, ProjectConfig, SnapshotConfig
from refactor_framework.plan.planner import create_plan
from refactor_framework.snapshot.capture import capture_snapshot


class TestCaptureSnapshot:
    def _make_config(self, tmp_path: Path, target_repo: Path) -> AppConfig:
        return AppConfig(
            project=ProjectConfig(
                target_repo=str(target_repo),
                increments_dir=str(tmp_path / "increments"),
            ),
            snapshot=SnapshotConfig(metrics_backend="radon"),
        )

    def _setup_increment(self, config: AppConfig, target_repo: Path):
        Path(config.project.increments_dir).mkdir(parents=True, exist_ok=True)
        return create_plan(config, file_patterns=["*.py"], description="Test capture")

    def test_captures_before_snapshot(self, tmp_path: Path, tmp_target_repo: Path):
        config = self._make_config(tmp_path, tmp_target_repo)
        record = self._setup_increment(config, tmp_target_repo)

        snapshot = capture_snapshot(config, record.increment_id, "before")

        assert snapshot.phase == "before"
        assert len(snapshot.files) == 2
        assert snapshot.total_loc > 0
        assert snapshot.timestamp != ""

        # Verify files were copied
        before_dir = Path(config.project.increments_dir) / record.increment_id / "before"
        assert (before_dir / "legacy_module.py").exists()
        assert (before_dir / "utils.py").exists()

        # Verify metrics JSON was written
        metrics_file = (
            Path(config.project.increments_dir) / record.increment_id / "before_metrics.json"
        )
        assert metrics_file.exists()

    def test_captures_after_snapshot(self, tmp_path: Path, tmp_target_repo: Path):
        config = self._make_config(tmp_path, tmp_target_repo)
        record = self._setup_increment(config, tmp_target_repo)

        snapshot = capture_snapshot(config, record.increment_id, "after")
        assert snapshot.phase == "after"

    def test_invalid_phase_raises(self, tmp_path: Path, tmp_target_repo: Path):
        config = self._make_config(tmp_path, tmp_target_repo)
        record = self._setup_increment(config, tmp_target_repo)

        with pytest.raises(ValueError, match="Phase must be"):
            capture_snapshot(config, record.increment_id, "middle")

    def test_metrics_computed_correctly(self, tmp_path: Path, tmp_target_repo: Path):
        config = self._make_config(tmp_path, tmp_target_repo)
        record = self._setup_increment(config, tmp_target_repo)

        snapshot = capture_snapshot(config, record.increment_id, "before")

        # All files should have metrics
        for fm in snapshot.files:
            assert fm.loc_total > 0
            assert fm.file_path != ""
