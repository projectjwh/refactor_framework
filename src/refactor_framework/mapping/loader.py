"""Load, validate, and manage construct mappings from YAML files."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from refactor_framework.models import ConstructMapping, MappingStatus

logger = logging.getLogger("refactor_framework.mapping")

_VALID_TYPES = {"1:1", "1:N", "N:1", "refactored", "removed", "new"}
_VALID_STATUSES = {s.value for s in MappingStatus}


def load_mappings(yaml_path: Path) -> tuple[list[ConstructMapping], str, str]:
    """Load construct mappings from a YAML file.

    Returns (mappings, source_language, target_language).
    """
    if not yaml_path.exists():
        raise FileNotFoundError(f"Mappings file not found: {yaml_path}")

    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    if not data or "mappings" not in data:
        raise ValueError(f"Mappings file must contain a 'mappings' key: {yaml_path}")

    source_lang = data.get("source_language", "")
    target_lang = data.get("target_language", "")

    mappings = []
    for i, m in enumerate(data["mappings"]):
        mapping = ConstructMapping(
            source_file=m.get("source_file", ""),
            source_construct=m.get("source_construct", ""),
            source_language=m.get("source_language", source_lang),
            target_file=m.get("target_file", ""),
            target_construct=m.get("target_construct", ""),
            target_language=m.get("target_language", target_lang),
            mapping_type=m.get("mapping_type", "1:1"),
            status=m.get("status", "TODO"),
            description=m.get("description", ""),
            source_line_start=_line(m, "source_lines", 0),
            source_line_end=_line(m, "source_lines", 1),
            target_line_start=_line(m, "target_lines", 0),
            target_line_end=_line(m, "target_lines", 1),
        )
        mappings.append(mapping)

    logger.info("Loaded %d construct mappings from %s", len(mappings), yaml_path.name)
    return mappings, source_lang, target_lang


def validate_mappings(
    mappings: list[ConstructMapping],
    source_files: list[str],
    target_files: list[str],
) -> list[str]:
    """Validate mappings against known file lists. Returns list of warnings."""
    warnings = []
    source_set = set(source_files)
    target_set = set(target_files)

    for i, m in enumerate(mappings):
        if m.mapping_type not in _VALID_TYPES:
            warnings.append(f"Mapping {i}: invalid type '{m.mapping_type}'")
        if m.status not in _VALID_STATUSES:
            warnings.append(f"Mapping {i}: invalid status '{m.status}'")
        if m.source_file and m.source_file not in source_set:
            warnings.append(f"Mapping {i}: source_file '{m.source_file}' not in plan source_files")
        if m.target_file and m.target_file not in target_set:
            warnings.append(f"Mapping {i}: target_file '{m.target_file}' not in plan target_files")
        if m.mapping_type != "removed" and not m.target_file:
            warnings.append(f"Mapping {i}: non-removed mapping missing target_file")
        if m.mapping_type != "new" and not m.source_file:
            warnings.append(f"Mapping {i}: non-new mapping missing source_file")

    # Check for duplicate source constructs within the same source file
    seen: dict[tuple[str, str], int] = {}
    for i, m in enumerate(mappings):
        key = (m.source_file, m.source_construct)
        if key in seen and m.source_file and m.source_construct:
            warnings.append(
                f"Mapping {i}: duplicate source_construct "
                f"'{m.source_construct}' in '{m.source_file}' "
                f"(first seen at mapping {seen[key]})"
            )
        else:
            seen[key] = i

    return warnings


def save_mappings(
    mappings: list[ConstructMapping],
    source_language: str,
    target_language: str,
    yaml_path: Path,
) -> None:
    """Serialize construct mappings to a YAML file."""
    data = {
        "source_language": source_language,
        "target_language": target_language,
        "mappings": [_mapping_to_dict(m) for m in mappings],
    }
    yaml_path.write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def compute_coverage(mappings: list[ConstructMapping]) -> dict:
    """Compute coverage statistics from construct mappings.

    Returns dict with total, complete, partial, todo, removed, pct_complete.
    """
    total = len(mappings)
    if total == 0:
        return {
            "total": 0, "complete": 0, "partial": 0,
            "todo": 0, "removed": 0, "pct_complete": 0.0,
        }

    counts = {"COMPLETE": 0, "PARTIAL": 0, "TODO": 0, "REMOVED": 0}
    for m in mappings:
        counts[m.status] = counts.get(m.status, 0) + 1

    actionable = total - counts["REMOVED"]
    pct = (counts["COMPLETE"] / actionable * 100.0) if actionable > 0 else 0.0

    return {
        "total": total,
        "complete": counts["COMPLETE"],
        "partial": counts["PARTIAL"],
        "todo": counts["TODO"],
        "removed": counts["REMOVED"],
        "pct_complete": round(pct, 1),
    }


def _mapping_to_dict(m: ConstructMapping) -> dict:
    """Convert a ConstructMapping to a clean dict for YAML output."""
    d = {
        "source_file": m.source_file,
        "source_construct": m.source_construct,
        "target_file": m.target_file,
        "target_construct": m.target_construct,
        "mapping_type": m.mapping_type,
        "status": m.status,
        "description": m.description,
    }
    if m.source_line_start is not None and m.source_line_end is not None:
        d["source_lines"] = [m.source_line_start, m.source_line_end]
    if m.target_line_start is not None and m.target_line_end is not None:
        d["target_lines"] = [m.target_line_start, m.target_line_end]
    return d


def _line(m: dict, key: str, idx: int) -> int | None:
    """Extract a line number from a [start, end] list, or None."""
    lines = m.get(key)
    if isinstance(lines, list) and len(lines) > idx:
        return lines[idx]
    return None
