"""Code metrics computation via radon and lizard."""

from __future__ import annotations

import logging
from pathlib import Path

from refactor_framework.models import FileMetrics

logger = logging.getLogger("refactor_framework.snapshot")

EXTENSION_LANG_MAP = {
    ".py": "Python", ".sas": "SAS", ".cpp": "C++", ".c": "C",
    ".java": "Java", ".js": "JavaScript", ".ts": "TypeScript",
    ".r": "R", ".sql": "SQL", ".rb": "Ruby", ".go": "Go",
    ".rs": "Rust", ".cs": "C#", ".scala": "Scala", ".kt": "Kotlin",
}

# Languages where radon works
_RADON_LANGUAGES = {"Python"}


def detect_language(file_path: str) -> str:
    """Detect programming language from file extension."""
    ext = Path(file_path).suffix.lower()
    return EXTENSION_LANG_MAP.get(ext, "Unknown")


def compute_file_metrics(file_path: Path, backend: str = "radon") -> FileMetrics:
    """Compute code metrics for a source file.

    Parameters
    ----------
    file_path : Path
        Absolute path to the source file.
    backend : str
        "radon", "lizard", or "both".
    """
    source = file_path.read_text(encoding="utf-8", errors="replace")
    lang = detect_language(str(file_path))
    metrics = FileMetrics(file_path=str(file_path), language=lang)

    if backend in ("radon", "both") and lang in _RADON_LANGUAGES:
        _apply_radon_metrics(source, metrics)
    elif backend == "radon" and lang not in _RADON_LANGUAGES:
        _apply_basic_metrics(source, metrics)

    if backend in ("lizard", "both"):
        _apply_lizard_metrics(str(file_path), metrics)

    # Fallback: if no metrics computed, at least count lines
    if metrics.loc_total == 0:
        _apply_basic_metrics(source, metrics)

    return metrics


def compute_directory_metrics(
    directory: Path,
    include_patterns: list[str],
    exclude_patterns: list[str],
    backend: str = "radon",
) -> list[FileMetrics]:
    """Compute metrics for all matching files in a directory."""
    import fnmatch

    results = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        name = path.name
        rel = str(path.relative_to(directory))

        if any(fnmatch.fnmatch(rel, ep) or fnmatch.fnmatch(name, ep) for ep in exclude_patterns):
            continue
        if not any(fnmatch.fnmatch(name, ip) for ip in include_patterns):
            continue

        try:
            fm = compute_file_metrics(path, backend)
            fm.file_path = rel
            results.append(fm)
        except Exception as exc:
            logger.warning("Failed to compute metrics for %s: %s", rel, exc)

    return results


def _apply_radon_metrics(source: str, metrics: FileMetrics) -> None:
    """Apply radon raw, complexity, and maintainability metrics."""
    from radon.complexity import cc_visit
    from radon.metrics import mi_visit
    from radon.raw import analyze

    # Raw metrics (LOC)
    try:
        raw = analyze(source)
        metrics.loc_total = raw.loc
        metrics.loc_code = raw.sloc
        metrics.loc_comment = raw.comments
        metrics.loc_blank = raw.blank
    except Exception:
        pass

    # Cyclomatic complexity
    try:
        blocks = cc_visit(source)
        if blocks:
            complexities = [b.complexity for b in blocks]
            metrics.cyclomatic_complexity_avg = sum(complexities) / len(complexities)
            metrics.cyclomatic_complexity_max = max(complexities)
            metrics.function_count = sum(1 for b in blocks if b.letter in ("F", "M"))
            metrics.class_count = sum(1 for b in blocks if b.letter == "C")
    except Exception:
        pass

    # Maintainability index
    try:
        metrics.maintainability_index = mi_visit(source, multi=True)
    except Exception:
        pass

    # Halstead metrics
    try:
        from radon.metrics import h_visit

        h_results = h_visit(source)
        if h_results:
            total = h_results[0] if not isinstance(h_results, list) else h_results[0]
            metrics.halstead_volume = getattr(total, "volume", 0.0) or 0.0
            metrics.halstead_difficulty = getattr(total, "difficulty", 0.0) or 0.0
            metrics.halstead_effort = getattr(total, "effort", 0.0) or 0.0
    except Exception:
        pass


def _apply_basic_metrics(source: str, metrics: FileMetrics) -> None:
    """Basic line-counting fallback for languages not supported by radon/lizard."""
    lines = source.splitlines()
    metrics.loc_total = len(lines)
    metrics.loc_blank = sum(1 for line in lines if not line.strip())
    # Simple comment heuristic: lines starting with common comment markers
    comment_markers = ("#", "//", "*", "/*", "--", ";")
    metrics.loc_comment = sum(
        1 for line in lines
        if line.strip() and line.strip()[0:2] in comment_markers
        or line.strip().startswith(comment_markers)
    )
    metrics.loc_code = metrics.loc_total - metrics.loc_blank - metrics.loc_comment


def _apply_lizard_metrics(file_path: str, metrics: FileMetrics) -> None:
    """Apply lizard complexity metrics (supplements radon for multi-language support)."""
    import lizard

    try:
        analysis = lizard.analyze_file(file_path)
        if analysis.function_list:
            complexities = [f.cyclomatic_complexity for f in analysis.function_list]
            # Only override if radon didn't already compute
            if metrics.cyclomatic_complexity_avg == 0.0:
                metrics.cyclomatic_complexity_avg = sum(complexities) / len(complexities)
                metrics.cyclomatic_complexity_max = max(complexities)
            if metrics.function_count == 0:
                metrics.function_count = len(analysis.function_list)
        if metrics.loc_total == 0:
            metrics.loc_total = analysis.nloc
    except Exception:
        pass
