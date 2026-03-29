"""Tests for increment plan creation."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from refactor_framework.config import AppConfig, ProjectConfig
from refactor_framework.plan.planner import create_plan, load_plan, resolve_files


class TestResolveFiles:
    def test_matches_py_files(self, tmp_target_repo: Path):
        files = resolve_files(str(tmp_target_repo), ["*.py"])
        assert "legacy_module.py" in files
        assert "utils.py" in files

    def test_no_matches_returns_empty(self, tmp_target_repo: Path):
        files = resolve_files(str(tmp_target_repo), ["*.rs"])
        assert files == []

    def test_raises_on_missing_repo(self):
        with pytest.raises(FileNotFoundError):
            resolve_files("/nonexistent/repo", ["*.py"])


class TestCreatePlan:
    def test_creates_plan_and_directory(self, tmp_path: Path, tmp_target_repo: Path):
        inc_dir = tmp_path / "increments"
        inc_dir.mkdir()
        config = AppConfig(
            project=ProjectConfig(
                target_repo=str(tmp_target_repo),
                increments_dir=str(inc_dir),
            )
        )

        record = create_plan(
            config,
            file_patterns=["*.py"],
            description="Test refactor",
            criteria=["All tests pass"],
        )

        assert record.status == "planned"
        assert len(record.plan.target_files) == 2
        assert record.plan.description == "Test refactor"
        assert record.plan.acceptance_criteria == ["All tests pass"]

        # Verify directory and plan.yaml were created
        plan_dir = inc_dir / record.increment_id
        assert plan_dir.is_dir()
        plan_yaml = plan_dir / "plan.yaml"
        assert plan_yaml.exists()

        data = yaml.safe_load(plan_yaml.read_text())
        assert data["description"] == "Test refactor"

    def test_raises_on_no_matching_files(self, tmp_path: Path, tmp_target_repo: Path):
        inc_dir = tmp_path / "increments"
        inc_dir.mkdir()
        config = AppConfig(
            project=ProjectConfig(
                target_repo=str(tmp_target_repo),
                increments_dir=str(inc_dir),
            )
        )
        with pytest.raises(ValueError, match="No files matched"):
            create_plan(config, file_patterns=["*.rs"], description="No files")


class TestLoadPlan:
    def test_loads_existing_plan(self, tmp_path: Path, tmp_target_repo: Path):
        inc_dir = tmp_path / "increments"
        inc_dir.mkdir()
        config = AppConfig(
            project=ProjectConfig(
                target_repo=str(tmp_target_repo),
                increments_dir=str(inc_dir),
            )
        )
        record = create_plan(config, file_patterns=["*.py"], description="Load test")

        loaded = load_plan(str(inc_dir), record.increment_id)
        assert loaded.description == "Load test"
        assert len(loaded.target_files) == 2

    def test_raises_on_missing_plan(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_plan(str(tmp_path), "99999999T999999")
