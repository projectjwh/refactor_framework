"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from refactor_framework.config import AppConfig


@pytest.fixture
def project_root() -> Path:
    """Return the refactor_framework project root."""
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def sample_config(tmp_path: Path) -> AppConfig:
    """Return an AppConfig with paths pointing to tmp dirs."""
    return AppConfig(
        project=AppConfig.project.__class__(
            name="test-project",
            target_repo=str(tmp_path / "target"),
            output_dir=str(tmp_path / "output"),
            increments_dir=str(tmp_path / "increments"),
            devlogs_dir=str(tmp_path / "devlogs"),
        ),
    )


@pytest.fixture
def tmp_target_repo(tmp_path: Path) -> Path:
    """Create a temporary target repo with sample Python files."""
    repo = tmp_path / "target"
    repo.mkdir()

    (repo / "legacy_module.py").write_text(
        '"""Legacy module with high complexity."""\n\n\n'
        "def process_data(data, mode, flag=False):\n"
        "    result = []\n"
        "    for item in data:\n"
        "        if mode == 'a':\n"
        "            if flag:\n"
        "                if item > 10:\n"
        "                    result.append(item * 2)\n"
        "                else:\n"
        "                    result.append(item)\n"
        "            else:\n"
        "                result.append(item + 1)\n"
        "        elif mode == 'b':\n"
        "            if flag:\n"
        "                result.append(item - 1)\n"
        "            else:\n"
        "                if item < 5:\n"
        "                    result.append(0)\n"
        "                else:\n"
        "                    result.append(item)\n"
        "        else:\n"
        "            result.append(item)\n"
        "    return result\n"
    )

    (repo / "utils.py").write_text(
        '"""Utility functions."""\n\n\n'
        "def add(a, b):\n"
        "    return a + b\n\n\n"
        "def multiply(a, b):\n"
        "    return a * b\n"
    )

    return repo


@pytest.fixture
def fixtures_dir() -> Path:
    """Return path to the test fixtures directory."""
    return Path(__file__).resolve().parent / "fixtures"
