"""Methodology document HTML rendering."""

from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from refactor_framework.models import IncrementRecord, MethodologyRecord
from refactor_framework.utils.paths import ensure_dir

logger = logging.getLogger("refactor_framework.methodology")

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def render_methodology(
    record: IncrementRecord,
    methodology: MethodologyRecord,
    output_path: Path,
    template_dir: str | None = None,
) -> Path:
    """Render the methodology HTML document."""
    tpl_dir = Path(template_dir) if template_dir else _TEMPLATES_DIR
    env = Environment(loader=FileSystemLoader(str(tpl_dir)), autoescape=False)
    template = env.get_template("methodology.html")

    # Count deviations
    deviations = sum(1 for s in methodology.spec_vs_actual if s.get("deviated"))
    matches = sum(1 for s in methodology.spec_vs_actual if not s.get("deviated"))

    context = {
        "record": asdict(record),
        "methodology": asdict(methodology),
        "spec_vs_actual": methodology.spec_vs_actual,
        "data_models": methodology.data_model_comparison,
        "decision_log": methodology.decision_log,
        "metrics": methodology.metrics_summary,
        "deviations": deviations,
        "matches": matches,
        "total_decisions": len(methodology.spec_vs_actual),
    }

    html = template.render(**context)
    ensure_dir(output_path.parent)
    output_path.write_text(html, encoding="utf-8")
    logger.info("Methodology document written to %s", output_path)
    return output_path
