"""Auto-scaffold construct mappings from SAS source files.

Parses SAS files to extract macros, PROC steps, DATA steps, and other
constructs, then generates a mapping YAML template with one entry per
construct found. This eliminates the manual YAML authoring bottleneck.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml

logger = logging.getLogger("refactor_framework.mapping")

# Patterns for SAS construct extraction
_MACRO_DEF = re.compile(r"^\s*%MACRO\s+(\w+)", re.IGNORECASE | re.MULTILINE)
_MACRO_END = re.compile(r"^\s*%MEND\s*(\w*)", re.IGNORECASE | re.MULTILINE)
_PROC_STEP = re.compile(
    r"^\s*PROC\s+(\w+)\b.*?;", re.IGNORECASE | re.MULTILINE
)
_DATA_STEP = re.compile(
    r"^\s*DATA\s+([\w.]+(?:\s*\([^)]*\))?)\s*;", re.IGNORECASE | re.MULTILINE
)
_INCLUDE = re.compile(r"^\s*%INCLUDE\s+", re.IGNORECASE | re.MULTILINE)


def extract_sas_constructs(file_path: Path) -> list[dict]:
    """Parse a SAS file and extract all identifiable constructs.

    Returns a list of dicts with: name, type, line_start, line_end, raw_header.
    """
    source = file_path.read_text(encoding="utf-8", errors="replace")
    lines = source.splitlines()
    constructs = []

    # Track macro boundaries for nested construct attribution
    macro_stack = []

    for i, line in enumerate(lines, 1):
        # Macro definitions
        m = _MACRO_DEF.match(line)
        if m:
            macro_name = m.group(1).upper()
            macro_stack.append({"name": macro_name, "line_start": i})

        m = _MACRO_END.match(line)
        if m:
            if macro_stack:
                macro = macro_stack.pop()
                constructs.append({
                    "name": macro["name"],
                    "type": "MACRO",
                    "line_start": macro["line_start"],
                    "line_end": i,
                    "raw_header": f"%MACRO {macro['name']}",
                })

        # PROC steps (outside macros get their own entry; inside macros = sub-construct)
        m = _PROC_STEP.match(line)
        if m:
            proc_name = m.group(1).upper()
            # Find the matching RUN; or QUIT;
            end_line = _find_step_end(lines, i - 1)
            parent = macro_stack[-1]["name"] if macro_stack else None
            name = f"{parent}::PROC_{proc_name}" if parent else f"PROC_{proc_name}"
            constructs.append({
                "name": name,
                "type": "PROC",
                "line_start": i,
                "line_end": end_line,
                "raw_header": line.strip()[:80],
            })

        # DATA steps
        m = _DATA_STEP.match(line)
        if m:
            ds_name = m.group(1).strip().split("(")[0].strip().upper()
            end_line = _find_step_end(lines, i - 1)
            parent = macro_stack[-1]["name"] if macro_stack else None
            name = f"{parent}::DATA_{ds_name}" if parent else f"DATA_{ds_name}"
            constructs.append({
                "name": name,
                "type": "DATA",
                "line_start": i,
                "line_end": end_line,
                "raw_header": line.strip()[:80],
            })

    return constructs


def scaffold_mappings(
    source_dir: Path,
    source_patterns: list[str],
    target_language: str = "Python",
) -> dict:
    """Generate a complete mapping YAML structure from SAS source files.

    Returns a dict ready for yaml.dump().
    """
    import fnmatch

    all_constructs = []

    for path in sorted(source_dir.rglob("*")):
        if not path.is_file():
            continue
        if not any(fnmatch.fnmatch(path.name, p) for p in source_patterns):
            continue

        rel = str(path.relative_to(source_dir))
        constructs = extract_sas_constructs(path)

        for c in constructs:
            all_constructs.append({
                "source_file": rel,
                "source_construct": c["name"],
                "target_file": "",  # To be filled by user
                "target_construct": "",  # To be filled by user
                "mapping_type": "refactored",
                "status": "TODO",
                "description": (
                    f"[AUTO-SCAFFOLDED] {c['type']} {c['name']} "
                    f"({c['line_end'] - c['line_start'] + 1} lines)"
                ),
                "source_lines": [c["line_start"], c["line_end"]],
            })

    # Detect source language from file extensions
    source_lang = "SAS"
    for c in all_constructs:
        ext = Path(c["source_file"]).suffix.lower()
        if ext == ".sas":
            source_lang = "SAS"
            break

    data = {
        "source_language": source_lang,
        "target_language": target_language,
        "mappings": all_constructs,
    }

    logger.info(
        "Scaffolded %d construct mappings from %s",
        len(all_constructs), source_dir,
    )
    return data


def scaffold_to_file(
    source_dir: Path,
    source_patterns: list[str],
    output_path: Path,
    target_language: str = "Python",
) -> int:
    """Generate a mapping YAML template and write to file. Returns construct count."""
    data = scaffold_mappings(source_dir, source_patterns, target_language)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return len(data["mappings"])


def _find_step_end(lines: list[str], start_idx: int) -> int:
    """Find the line number of the RUN; or QUIT; ending a PROC/DATA step."""
    for i in range(start_idx + 1, len(lines)):
        stripped = lines[i].strip().upper()
        if stripped in ("RUN;", "QUIT;") or stripped.startswith(("RUN;", "QUIT;")):
            return i + 1  # 1-indexed
    return len(lines)  # EOF if no explicit end found
