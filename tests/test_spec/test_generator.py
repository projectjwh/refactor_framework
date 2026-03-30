"""Tests for architecture spec generation."""

from __future__ import annotations

from pathlib import Path

import yaml

from refactor_framework.config import AppConfig, ProjectConfig
from refactor_framework.plan.planner import create_plan
from refactor_framework.spec.generator import (
    generate_spec,
    load_spec_json,
    save_spec,
    spec_to_markdown,
)


class TestGenerateSpec:
    def _setup(self, tmp_path: Path):
        repo = tmp_path / "target"
        repo.mkdir()
        (repo / "main.py").write_text("x = 1\n")
        inc_dir = tmp_path / "increments"
        inc_dir.mkdir()
        config = AppConfig(
            project=ProjectConfig(
                target_repo=str(repo), increments_dir=str(inc_dir),
            )
        )
        record = create_plan(config, file_patterns=["*.py"], description="Test spec")
        # Add a construct mapping to the plan
        plan_file = inc_dir / record.increment_id / "plan.yaml"
        plan_data = yaml.safe_load(plan_file.read_text())
        plan_data["construct_mappings"] = [{
            "source_file": "old.sas",
            "source_construct": "PROC_SORT",
            "source_language": "SAS",
            "target_file": "main.py",
            "target_construct": "sort_data",
            "target_language": "Python",
            "mapping_type": "refactored",
            "status": "TODO",
            "description": "Sort replaced by Polars",
        }]
        plan_data["migration"] = {
            "mode": "cross-language", "source_repo": "",
            "source_language": "SAS", "target_language": "Python",
        }
        plan_file.write_text(yaml.dump(plan_data, default_flow_style=False))
        return config, record.increment_id

    def test_generates_spec_with_module_decisions(self, tmp_path: Path):
        config, inc_id = self._setup(tmp_path)
        spec = generate_spec(config, inc_id)
        assert spec.increment_id == inc_id
        assert len(spec.module_decisions) == 1
        assert spec.module_decisions[0].source_construct == "PROC_SORT"
        assert len(spec.module_decisions[0].alternatives) == 2

    def test_generates_risks(self, tmp_path: Path):
        config, inc_id = self._setup(tmp_path)
        spec = generate_spec(config, inc_id)
        assert len(spec.risks) >= 2

    def test_generates_scaling_considerations(self, tmp_path: Path):
        config, inc_id = self._setup(tmp_path)
        spec = generate_spec(config, inc_id)
        assert len(spec.scaling_considerations) >= 1

    def test_empty_mappings_produces_empty_decisions(self, tmp_path: Path):
        repo = tmp_path / "target"
        repo.mkdir()
        (repo / "main.py").write_text("x = 1\n")
        inc_dir = tmp_path / "increments"
        inc_dir.mkdir()
        config = AppConfig(
            project=ProjectConfig(
                target_repo=str(repo), increments_dir=str(inc_dir),
            )
        )
        record = create_plan(config, file_patterns=["*.py"], description="No mappings")
        spec = generate_spec(config, record.increment_id)
        assert spec.module_decisions == []


class TestSpecToMarkdown:
    def test_renders_markdown(self, tmp_path: Path):
        config, inc_id = TestGenerateSpec()._setup(tmp_path)
        spec = generate_spec(config, inc_id)
        md = spec_to_markdown(spec)
        assert "# Architecture Spec:" in md
        assert "PROC_SORT" in md
        assert "Alternatives Considered" in md
        assert "Risks" in md


class TestSaveAndLoadSpec:
    def test_roundtrip(self, tmp_path: Path):
        config, inc_id = TestGenerateSpec()._setup(tmp_path)
        spec = generate_spec(config, inc_id)
        save_spec(config, inc_id, spec)

        loaded = load_spec_json(config, inc_id)
        assert loaded is not None
        assert loaded.increment_id == inc_id
        assert len(loaded.module_decisions) == 1
        assert loaded.module_decisions[0].source_construct == "PROC_SORT"
        assert len(loaded.module_decisions[0].alternatives) == 2

    def test_load_returns_none_if_missing(self, tmp_path: Path):
        config = AppConfig(
            project=ProjectConfig(increments_dir=str(tmp_path))
        )
        assert load_spec_json(config, "nonexistent") is None
