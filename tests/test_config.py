"""Tests for configuration loading."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from refactor_framework.config import AppConfig, _build_dataclass, load_config


class TestBuildDataclass:
    def test_returns_defaults_on_none(self):
        cfg = _build_dataclass(AppConfig, None)
        assert cfg.project.name == "refactoring-project"
        assert cfg.snapshot.metrics_backend == "radon"

    def test_overrides_fields(self):
        data = {"project": {"name": "my-project", "target_repo": "/tmp/repo"}}
        cfg = _build_dataclass(AppConfig, data)
        assert cfg.project.name == "my-project"
        assert cfg.project.target_repo == "/tmp/repo"
        # Defaults preserved for unspecified fields
        assert cfg.project.output_dir == "output"

    def test_ignores_unknown_keys(self):
        data = {"project": {"name": "test", "unknown_field": 42}}
        cfg = _build_dataclass(AppConfig, data)
        assert cfg.project.name == "test"

    def test_nested_dataclass_hydration(self):
        data = {
            "execute": {"default_model": "claude-opus-4-20250514", "cost_per_input_token": 0.01},
            "archive": {"ledger_backend": "sqlite"},
        }
        cfg = _build_dataclass(AppConfig, data)
        assert cfg.execute.default_model == "claude-opus-4-20250514"
        assert cfg.execute.cost_per_input_token == 0.01
        assert cfg.archive.ledger_backend == "sqlite"


class TestLoadConfig:
    def test_loads_from_yaml(self, tmp_path: Path):
        config_data = {
            "project": {"name": "yaml-test", "target_repo": "/some/path"},
            "snapshot": {"metrics_backend": "both"},
        }
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(yaml.dump(config_data))

        cfg = load_config(str(config_file))
        assert cfg.project.name == "yaml-test"
        assert cfg.snapshot.metrics_backend == "both"
        # Defaults preserved
        assert cfg.report.diff_style == "side-by-side"

    def test_raises_on_missing_file(self):
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/path/config.yaml")

    def test_handles_empty_yaml(self, tmp_path: Path):
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("")
        cfg = load_config(str(config_file))
        assert cfg.project.name == "refactoring-project"
