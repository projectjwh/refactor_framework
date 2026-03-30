"""Tests for auto-scaffold from SAS source."""

from __future__ import annotations

from pathlib import Path

from refactor_framework.mapping.scaffold import (
    extract_sas_constructs,
    scaffold_to_file,
)


class TestExtractSasConstructs:
    def test_extracts_macro(self, tmp_path: Path):
        sas = tmp_path / "test.sas"
        sas.write_text(
            "%MACRO DO_STUFF(X);\n"
            "  DATA work.out; SET work.in; RUN;\n"
            "%MEND DO_STUFF;\n"
        )
        constructs = extract_sas_constructs(sas)
        macros = [c for c in constructs if c["type"] == "MACRO"]
        assert len(macros) == 1
        assert macros[0]["name"] == "DO_STUFF"

    def test_extracts_proc(self, tmp_path: Path):
        sas = tmp_path / "test.sas"
        sas.write_text("PROC SORT DATA=work.x; BY id; RUN;\n")
        constructs = extract_sas_constructs(sas)
        procs = [c for c in constructs if c["type"] == "PROC"]
        assert len(procs) == 1
        assert "SORT" in procs[0]["name"]

    def test_extracts_data_step(self, tmp_path: Path):
        sas = tmp_path / "test.sas"
        sas.write_text("DATA work.output; SET work.input; x = 1; RUN;\n")
        constructs = extract_sas_constructs(sas)
        data_steps = [c for c in constructs if c["type"] == "DATA"]
        assert len(data_steps) == 1

    def test_nested_constructs_have_parent(self, tmp_path: Path):
        sas = tmp_path / "test.sas"
        sas.write_text(
            "%MACRO OUTER;\n"
            "  PROC SQL; CREATE TABLE x AS SELECT 1; QUIT;\n"
            "%MEND OUTER;\n"
        )
        constructs = extract_sas_constructs(sas)
        procs = [c for c in constructs if c["type"] == "PROC"]
        assert len(procs) >= 1
        assert "OUTER" in procs[0]["name"]


class TestScaffoldToFile:
    def test_generates_yaml(self, tmp_path: Path):
        sas_dir = tmp_path / "sas"
        sas_dir.mkdir()
        (sas_dir / "test.sas").write_text(
            "%MACRO PROCESS;\n"
            "  DATA work.x;\n"
            "    SET y;\n"
            "  RUN;\n"
            "%MEND PROCESS;\n"
        )
        out = tmp_path / "mappings.yaml"
        count = scaffold_to_file(sas_dir, ["*.sas"], out)
        assert count >= 1
        assert out.exists()
        import yaml
        data = yaml.safe_load(out.read_text())
        assert data["source_language"] == "SAS"
        assert len(data["mappings"]) >= 1

    def test_on_real_sas_files(self, fixtures_dir: Path):
        """Test against the actual legacy SAS codebase."""
        sas_dir = fixtures_dir.parent.parent / "legacy_sas_codebase" / "programs"
        if not sas_dir.exists():
            return  # Skip if not present
        constructs = extract_sas_constructs(sas_dir / "02_enroll_process.sas")
        assert len(constructs) >= 5  # macro + multiple PROC/DATA steps
