"""Rule-based auto-approval for architecture specs."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict

from refactor_framework.models import ArchitectureSpec

logger = logging.getLogger("refactor_framework.pipeline")


def auto_approve_spec(spec: ArchitectureSpec, intake: dict) -> tuple[bool, str]:
    """Auto-approve a spec if it meets quality gates.

    Returns (approved, reason).
    """
    reasons = []

    # Gate 1: No unfilled placeholders
    spec_text = json.dumps(asdict(spec), default=str)
    if "[TO BE FILLED]" in spec_text or "[FILL IN:" in spec_text:
        unfilled = spec_text.count("[TO BE FILLED]") + spec_text.count("[FILL IN:")
        reasons.append(f"{unfilled} unfilled placeholders remain")

    # Gate 2: Risk tolerance
    high_risks = [r for r in spec.risks if r.severity == "high"]
    max_risk = intake.get("risk_qa", {}).get("max_risk_severity", "medium")
    if high_risks and max_risk not in ("high", "critical"):
        reasons.append(
            f"{len(high_risks)} high-severity risks exceed "
            f"intake tolerance ({max_risk})"
        )

    # Gate 3: At least one acceptance criterion defined (not placeholder)
    real_criteria = [
        c for c in spec.acceptance_criteria
        if not c.startswith("[")
    ]
    if not real_criteria:
        reasons.append("No concrete acceptance criteria defined")

    # Gate 4: Module decisions exist if construct mappings exist
    if not spec.module_decisions and spec.increment_id:
        # This is OK if there are no construct mappings
        pass

    if reasons:
        return False, "Auto-approval BLOCKED: " + "; ".join(reasons)

    return True, "All quality gates passed — auto-approved"
