"""Tests for diff generation."""

from __future__ import annotations

from pathlib import Path

from refactor_framework.report.diff import generate_all_diffs, generate_file_diff


class TestGenerateFileDiff:
    def test_detects_changes(self, tmp_path: Path):
        before = tmp_path / "before.py"
        after = tmp_path / "after.py"
        before.write_text("def hello():\n    return 'world'\n")
        after.write_text("def hello():\n    return 'universe'\n")

        result = generate_file_diff(before, after, "hello.py")

        assert result["changed"] is True
        assert result["added"] > 0
        assert result["removed"] > 0
        assert "html_diff" in result
        assert "unified_diff" in result

    def test_no_changes(self, tmp_path: Path):
        f = tmp_path / "same.py"
        f.write_text("x = 1\n")

        result = generate_file_diff(f, f, "same.py")
        assert result["changed"] is False
        assert result["added"] == 0
        assert result["removed"] == 0

    def test_unified_style(self, tmp_path: Path):
        before = tmp_path / "a.py"
        after = tmp_path / "b.py"
        before.write_text("line1\nline2\n")
        after.write_text("line1\nline3\n")

        result = generate_file_diff(before, after, "test.py", style="unified")
        assert "diff-add" in result["html_diff"]
        assert "diff-del" in result["html_diff"]


class TestGenerateAllDiffs:
    def test_generates_diffs_for_all_files(self, tmp_path: Path):
        inc_dir = tmp_path / "increment"
        before_dir = inc_dir / "before"
        after_dir = inc_dir / "after"
        before_dir.mkdir(parents=True)
        after_dir.mkdir(parents=True)

        (before_dir / "a.py").write_text("x = 1\n")
        (after_dir / "a.py").write_text("x = 2\n")
        (before_dir / "b.py").write_text("y = 1\n")
        (after_dir / "b.py").write_text("y = 1\n")

        diffs = generate_all_diffs(inc_dir, ["a.py", "b.py"])
        assert len(diffs) == 2

        changed = [d for d in diffs if d["changed"]]
        assert len(changed) == 1
        assert changed[0]["rel_path"] == "a.py"

    def test_handles_missing_after_file(self, tmp_path: Path):
        inc_dir = tmp_path / "increment"
        before_dir = inc_dir / "before"
        before_dir.mkdir(parents=True)
        (inc_dir / "after").mkdir(parents=True)
        (before_dir / "removed.py").write_text("x = 1\n")

        diffs = generate_all_diffs(inc_dir, ["removed.py"])
        assert len(diffs) == 1
        assert diffs[0]["changed"] is True
        assert diffs[0]["removed"] > 0
