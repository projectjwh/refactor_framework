"""Tests for spec approval gate."""

from __future__ import annotations

from pathlib import Path

import pytest

from refactor_framework.config import AppConfig, ProjectConfig
from refactor_framework.plan.planner import create_plan
from refactor_framework.spec.approval import check_approval, has_spec, record_approval
from refactor_framework.spec.generator import generate_spec, save_spec


class TestApproval:
    def _setup(self, tmp_path: Path):
        repo = tmp_path / "target"
        repo.mkdir()
        (repo / "a.py").write_text("x = 1\n")
        inc_dir = tmp_path / "increments"
        inc_dir.mkdir()
        config = AppConfig(
            project=ProjectConfig(
                target_repo=str(repo), increments_dir=str(inc_dir),
            )
        )
        record = create_plan(config, file_patterns=["*.py"], description="Approval test")
        spec = generate_spec(config, record.increment_id)
        save_spec(config, record.increment_id, spec)
        return config, record.increment_id

    def test_has_spec_true_after_save(self, tmp_path: Path):
        config, inc_id = self._setup(tmp_path)
        assert has_spec(config, inc_id) is True

    def test_has_spec_false_when_missing(self, tmp_path: Path):
        config = AppConfig(
            project=ProjectConfig(increments_dir=str(tmp_path))
        )
        assert has_spec(config, "nonexistent") is False

    def test_check_approval_false_before_approve(self, tmp_path: Path):
        config, inc_id = self._setup(tmp_path)
        assert check_approval(config, inc_id) is False

    def test_record_approval_sets_flag(self, tmp_path: Path):
        config, inc_id = self._setup(tmp_path)
        approval = record_approval(config, inc_id, "Alice", "LGTM")
        assert approval.approved_by == "Alice"
        assert approval.notes == "LGTM"
        assert check_approval(config, inc_id) is True

    def test_approval_raises_without_spec(self, tmp_path: Path):
        config = AppConfig(
            project=ProjectConfig(increments_dir=str(tmp_path))
        )
        with pytest.raises(FileNotFoundError):
            record_approval(config, "nonexistent", "Bob")
