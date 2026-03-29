"""Tests for execution tracking."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from refactor_framework.config import AppConfig, ExecuteConfig, ProjectConfig
from refactor_framework.execute.tracker import (
    load_execution_data,
    start_execution,
    stop_execution,
)


class TestExecutionTracker:
    def _make_config(self, tmp_path: Path) -> AppConfig:
        inc_dir = tmp_path / "increments"
        inc_dir.mkdir()
        return AppConfig(
            project=ProjectConfig(increments_dir=str(inc_dir)),
            execute=ExecuteConfig(
                default_model="test-model",
                cost_per_input_token=0.001,
                cost_per_output_token=0.002,
            ),
        )

    def _create_increment_dir(self, config: AppConfig, inc_id: str) -> Path:
        inc_dir = Path(config.project.increments_dir) / inc_id
        inc_dir.mkdir(parents=True)
        return inc_dir

    def test_start_creates_file(self, tmp_path: Path):
        config = self._make_config(tmp_path)
        inc_id = "20260326T100000"
        self._create_increment_dir(config, inc_id)

        ts = start_execution(config, inc_id)
        assert ts != ""

        start_file = Path(config.project.increments_dir) / inc_id / "execution_start.json"
        assert start_file.exists()
        data = json.loads(start_file.read_text())
        assert "start_time" in data

    def test_start_raises_on_missing_dir(self, tmp_path: Path):
        config = self._make_config(tmp_path)
        with pytest.raises(FileNotFoundError):
            start_execution(config, "nonexistent")

    def test_stop_computes_duration_and_cost(self, tmp_path: Path):
        config = self._make_config(tmp_path)
        inc_id = "20260326T100000"
        self._create_increment_dir(config, inc_id)

        start_execution(config, inc_id)
        time_rec, token_usage = stop_execution(
            config, inc_id, tokens_input=1000, tokens_output=500,
        )

        assert time_rec.duration_seconds >= 0
        assert time_rec.start_time != ""
        assert time_rec.end_time != ""
        assert token_usage.total_tokens == 1500
        assert token_usage.model == "test-model"
        assert token_usage.cost_estimate_usd == round(1000 * 0.001 + 500 * 0.002, 6)

    def test_stop_raises_without_start(self, tmp_path: Path):
        config = self._make_config(tmp_path)
        inc_id = "20260326T100000"
        self._create_increment_dir(config, inc_id)

        with pytest.raises(FileNotFoundError, match="execution_start.json"):
            stop_execution(config, inc_id)

    def test_load_execution_data(self, tmp_path: Path):
        config = self._make_config(tmp_path)
        inc_id = "20260326T100000"
        self._create_increment_dir(config, inc_id)

        start_execution(config, inc_id)
        stop_execution(config, inc_id, tokens_input=200, tokens_output=100)

        result = load_execution_data(config.project.increments_dir, inc_id)
        assert result is not None
        time_rec, token_usage = result
        assert token_usage.total_tokens == 300

    def test_load_returns_none_if_missing(self, tmp_path: Path):
        result = load_execution_data(str(tmp_path), "nonexistent")
        assert result is None
