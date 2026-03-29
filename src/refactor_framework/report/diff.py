"""File-level diff generation between before and after snapshots."""

from __future__ import annotations

import difflib
import logging
from pathlib import Path

logger = logging.getLogger("refactor_framework.report")


def generate_file_diff(
    before_path: Path,
    after_path: Path,
    rel_path: str,
    style: str = "side-by-side",
) -> dict:
    """Generate diff for a single file.

    Returns a dict with:
        - rel_path: relative file path
        - unified_diff: unified diff text
        - html_diff: HTML side-by-side or unified diff
        - added: number of added lines
        - removed: number of removed lines
        - changed: bool indicating if file changed
    """
    before_lines = _read_lines(before_path)
    after_lines = _read_lines(after_path)

    # Unified diff
    unified = list(difflib.unified_diff(
        before_lines, after_lines,
        fromfile=f"before/{rel_path}",
        tofile=f"after/{rel_path}",
        lineterm="",
    ))

    # Count additions/removals
    added = sum(1 for line in unified if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in unified if line.startswith("-") and not line.startswith("---"))

    # HTML diff
    if style == "side-by-side":
        html_diff = difflib.HtmlDiff(tabsize=4, wrapcolumn=80).make_table(
            before_lines, after_lines,
            fromdesc=f"before/{rel_path}",
            todesc=f"after/{rel_path}",
            context=True,
            numlines=3,
        )
    else:
        html_diff = _unified_to_html(unified)

    return {
        "rel_path": rel_path,
        "unified_diff": "\n".join(unified),
        "html_diff": html_diff,
        "added": added,
        "removed": removed,
        "changed": len(unified) > 0,
    }


def generate_all_diffs(
    increment_dir: Path,
    target_files: list[str],
    style: str = "side-by-side",
) -> list[dict]:
    """Generate diffs for all files in an increment."""
    before_dir = increment_dir / "before"
    after_dir = increment_dir / "after"
    results = []

    for rel_path in target_files:
        before_path = before_dir / rel_path
        after_path = after_dir / rel_path

        if before_path.exists() and after_path.exists():
            diff = generate_file_diff(before_path, after_path, rel_path, style)
            results.append(diff)
        elif before_path.exists():
            results.append({
                "rel_path": rel_path,
                "unified_diff": f"--- File removed: {rel_path}",
                "html_diff": f"<p class='removed'>File removed: {rel_path}</p>",
                "added": 0,
                "removed": sum(1 for _ in _read_lines(before_path)),
                "changed": True,
            })
        elif after_path.exists():
            results.append({
                "rel_path": rel_path,
                "unified_diff": f"+++ File added: {rel_path}",
                "html_diff": f"<p class='added'>File added: {rel_path}</p>",
                "added": sum(1 for _ in _read_lines(after_path)),
                "removed": 0,
                "changed": True,
            })

    return results


def _read_lines(path: Path) -> list[str]:
    """Read file lines, handling encoding errors."""
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []


def _unified_to_html(unified_lines: list[str]) -> str:
    """Convert unified diff lines to simple HTML."""
    parts = ['<div class="unified-diff"><pre>']
    for line in unified_lines:
        if line.startswith("+++") or line.startswith("---"):
            parts.append(f'<span class="diff-header">{_escape(line)}</span>')
        elif line.startswith("@@"):
            parts.append(f'<span class="diff-hunk">{_escape(line)}</span>')
        elif line.startswith("+"):
            parts.append(f'<span class="diff-add">{_escape(line)}</span>')
        elif line.startswith("-"):
            parts.append(f'<span class="diff-del">{_escape(line)}</span>')
        else:
            parts.append(_escape(line))
    parts.append("</pre></div>")
    return "\n".join(parts)


def _escape(text: str) -> str:
    """Escape HTML special characters."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
