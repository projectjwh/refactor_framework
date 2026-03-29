"""Tests for construct mapping loader."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from refactor_framework.mapping.loader import (
    compute_coverage,
    load_mappings,
    save_mappings,
    validate_mappings,
)
from refactor_framework.models import ConstructMapping


class TestLoadMappings:
    def test_loads_sample_fixture(self, fixtures_dir: Path):
        mappings, src_lang, tgt_lang = load_mappings(fixtures_dir / "sample_mappings.yaml")
        assert src_lang == "SAS"
        assert tgt_lang == "Python"
        assert len(mappings) == 6
        assert mappings[0].source_construct == "PROCESS_ENROLLMENT"
        assert mappings[0].target_construct == "process_partition"
        assert mappings[0].status == "COMPLETE"

    def test_line_ranges_parsed(self, fixtures_dir: Path):
        mappings, _, _ = load_mappings(fixtures_dir / "sample_mappings.yaml")
        assert mappings[0].source_line_start == 35
        assert mappings[0].source_line_end == 449
        assert mappings[0].target_line_start == 52
        assert mappings[0].target_line_end == 117

    def test_missing_line_ranges_are_none(self, fixtures_dir: Path):
        mappings, _, _ = load_mappings(fixtures_dir / "sample_mappings.yaml")
        # The "STEP_5_CONCATENATE" mapping has no line ranges
        step5 = [m for m in mappings if m.source_construct == "STEP_5_CONCATENATE"][0]
        assert step5.source_line_start is None
        assert step5.target_line_end is None

    def test_raises_on_missing_file(self):
        with pytest.raises(FileNotFoundError):
            load_mappings(Path("/nonexistent.yaml"))

    def test_raises_on_missing_mappings_key(self, tmp_path: Path):
        f = tmp_path / "bad.yaml"
        f.write_text(yaml.dump({"source_language": "SAS"}))
        with pytest.raises(ValueError, match="mappings"):
            load_mappings(f)


class TestValidateMappings:
    def test_valid_mappings_no_warnings(self, fixtures_dir: Path):
        mappings, _, _ = load_mappings(fixtures_dir / "sample_mappings.yaml")
        source_files = ["00_config.sas", "01_enroll_driver.sas", "02_enroll_process.sas"]
        target_files = ["config.py", "enroll_driver.py", "enroll_process.py"]
        warnings = validate_mappings(mappings, source_files, target_files)
        assert warnings == []

    def test_warns_on_unknown_source_file(self):
        mappings = [ConstructMapping(
            source_file="missing.sas", source_construct="X",
            target_file="a.py", target_construct="Y",
        )]
        warnings = validate_mappings(mappings, [], ["a.py"])
        assert any("source_file" in w for w in warnings)

    def test_warns_on_invalid_type(self):
        mappings = [ConstructMapping(
            source_file="a.sas", source_construct="X",
            target_file="a.py", target_construct="Y",
            mapping_type="invalid",
        )]
        warnings = validate_mappings(mappings, ["a.sas"], ["a.py"])
        assert any("invalid type" in w for w in warnings)


class TestComputeCoverage:
    def test_all_complete(self):
        mappings = [
            ConstructMapping(status="COMPLETE"),
            ConstructMapping(status="COMPLETE"),
        ]
        cov = compute_coverage(mappings)
        assert cov["total"] == 2
        assert cov["complete"] == 2
        assert cov["pct_complete"] == 100.0

    def test_mixed_statuses(self):
        mappings = [
            ConstructMapping(status="COMPLETE"),
            ConstructMapping(status="PARTIAL"),
            ConstructMapping(status="TODO"),
            ConstructMapping(status="REMOVED"),
        ]
        cov = compute_coverage(mappings)
        assert cov["total"] == 4
        assert cov["complete"] == 1
        assert cov["partial"] == 1
        assert cov["todo"] == 1
        assert cov["removed"] == 1
        # pct_complete = 1/3 (excluding REMOVED) = 33.3%
        assert cov["pct_complete"] == 33.3

    def test_empty_mappings(self):
        cov = compute_coverage([])
        assert cov["total"] == 0
        assert cov["pct_complete"] == 0.0

    def test_from_fixture(self, fixtures_dir: Path):
        mappings, _, _ = load_mappings(fixtures_dir / "sample_mappings.yaml")
        cov = compute_coverage(mappings)
        assert cov["total"] == 6
        assert cov["complete"] == 5
        assert cov["partial"] == 1


class TestSaveMappings:
    def test_roundtrip(self, fixtures_dir: Path, tmp_path: Path):
        mappings, src, tgt = load_mappings(fixtures_dir / "sample_mappings.yaml")
        out = tmp_path / "output.yaml"
        save_mappings(mappings, src, tgt, out)

        reloaded, src2, tgt2 = load_mappings(out)
        assert src2 == "SAS"
        assert tgt2 == "Python"
        assert len(reloaded) == len(mappings)
        assert reloaded[0].source_construct == mappings[0].source_construct
