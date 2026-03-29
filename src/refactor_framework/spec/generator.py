"""Architecture spec generation — auto-fills from plan and construct mappings."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from refactor_framework.config import AppConfig
from refactor_framework.models import (
    ArchitectureSpec,
    DataModelChange,
    DesignAlternative,
    ModuleDecision,
    RiskItem,
    ScalingConsideration,
)
from refactor_framework.plan.planner import load_plan
from refactor_framework.utils.paths import ensure_dir

logger = logging.getLogger("refactor_framework.spec")


def generate_spec(config: AppConfig, increment_id: str) -> ArchitectureSpec:
    """Generate an architecture spec pre-filled from the plan and construct mappings.

    If intake.yaml exists, uses it to enrich risks, scaling, and preferences.
    """
    plan = load_plan(config.project.increments_dir, increment_id)

    # Load intake data if available
    from refactor_framework.config import find_project_root
    from refactor_framework.intake.interview import load_intake

    intake = load_intake(find_project_root() / "intake.yaml")

    # Build module decisions from construct mappings
    module_decisions = []
    for m in plan.construct_mappings:
        decision = ModuleDecision(
            source_construct=m.source_construct,
            source_file=m.source_file,
            source_description=m.description or f"{m.mapping_type} of {m.source_construct}",
            target_approach=(
                f"Implement as {m.target_construct} in {m.target_file}"
                if m.target_file else ""
            ),
            alternatives=[
                DesignAlternative(
                    option_name="A: Direct translation",
                    description="Line-by-line equivalent in target language",
                    pros=["Preserves original logic", "Easy to verify"],
                    cons=["May miss target idioms", "Could carry tech debt"],
                ),
                DesignAlternative(
                    option_name="B: Idiomatic rewrite",
                    description="Redesign using target language best practices",
                    pros=["Cleaner code", "Better performance", "Easier maintenance"],
                    cons=["Harder to verify equivalence", "More effort"],
                    chosen=True,
                    rationale="[TO BE FILLED — explain why this approach was chosen]",
                ),
            ],
            chosen_alternative="B: Idiomatic rewrite",
            rationale="[TO BE FILLED]",
        )
        module_decisions.append(decision)

    # Auto-detect scaling considerations
    scaling = _detect_scaling_considerations(plan)

    # Risks — enriched from intake if available
    risks = [
        RiskItem(
            description="Behavioral divergence from source",
            severity="high", likelihood="medium",
            mitigation="Run equivalence testing (validate command)",
        ),
        RiskItem(
            description="Missing edge cases not covered by test data",
            severity="medium", likelihood="medium",
            mitigation="Test with production-scale sample before cutover",
        ),
    ]
    if intake:
        codebase = intake.get("codebase", {})
        if codebase.get("test_coverage") in ("none", "minimal"):
            risks.append(RiskItem(
                description=f"Low test coverage ({codebase['test_coverage']})",
                severity="high", likelihood="high",
                mitigation="Write characterization tests before migration",
            ))
        if codebase.get("data_sensitivity", "").startswith("regulated"):
            risks.append(RiskItem(
                description=f"Regulated data ({codebase['data_sensitivity']})",
                severity="high", likelihood="low",
                mitigation="Ensure no PHI/PII in logs, validate compliance",
            ))
        for pain in codebase.get("pain_points", []):
            if pain:
                risks.append(RiskItem(
                    description=f"Known pain point: {pain}",
                    severity="medium", likelihood="high",
                    mitigation="[TO BE FILLED]",
                ))

    # Architecture overview — enriched from intake
    is_cross = plan.migration.mode == "cross-language"
    parts = []
    if is_cross:
        parts.append(
            f"Migration from {plan.migration.source_language} to "
            f"{plan.migration.target_language}."
        )
        parts.append(
            f"**Source files ({len(plan.source_files)}):** "
            f"{', '.join(plan.source_files)}"
        )
        parts.append(
            f"**Target files ({len(plan.target_files)}):** "
            f"{', '.join(plan.target_files)}"
        )
    else:
        parts.append(f"Refactoring {len(plan.target_files)} files in place.")
        parts.append(f"**Target files:** {', '.join(plan.target_files)}")

    if intake:
        goals = intake.get("goals", {})
        tech = intake.get("technical", {})
        parts.append(f"\n**Motivation:** {goals.get('motivation', 'N/A')}")
        parts.append(f"**Timeline:** {goals.get('timeline', 'N/A')}")
        parts.append(f"**Success:** {goals.get('success_definition', 'N/A')}")
        if tech.get("key_libraries"):
            parts.append(
                f"**Target stack:** {', '.join(tech['key_libraries'])}"
            )
        if tech.get("parallelism") and tech["parallelism"] != "none":
            parts.append(f"**Parallelism:** {tech['parallelism']}")
        if tech.get("prefer_idiomatic"):
            parts.append("**Style:** Idiomatic target-language patterns preferred")

    parts.append("\n[FILL IN: Main entry points, module structure, call graph]")
    overview = "\n\n".join(parts)

    spec = ArchitectureSpec(
        increment_id=increment_id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        architecture_overview=overview,
        module_decisions=module_decisions,
        scaling_considerations=scaling,
        data_model_changes=[
            DataModelChange(
                entity_name="[FILL IN: Primary output entity]",
                changes=["[FILL IN: Schema changes]"],
                grain_change="[FILL IN: e.g., row-per-month -> row-per-year]",
            ),
        ],
        risks=risks,
        acceptance_criteria=plan.acceptance_criteria[:] if plan.acceptance_criteria else [
            "[FILL IN: Acceptance criteria]"
        ],
    )

    return spec


def spec_to_markdown(spec: ArchitectureSpec) -> str:
    """Render an ArchitectureSpec to structured markdown."""
    lines = [
        f"# Architecture Spec: {spec.increment_id}",
        "",
        f"**Generated:** {spec.generated_at[:19]}",
        f"**Status:** {'APPROVED' if spec.approval else 'PENDING REVIEW'}",
        "",
        "---",
        "",
        "## 1. Architecture Overview",
        "",
        spec.architecture_overview,
        "",
        "---",
        "",
        "## 2. Module-by-Module Decisions",
        "",
    ]

    for i, md in enumerate(spec.module_decisions, 1):
        lines.append(f"### 2.{i} {md.source_construct} ({md.source_file})")
        lines.append("")
        lines.append(f"**What it does (source):** {md.source_description}")
        lines.append("")
        lines.append(f"**Target approach:** {md.target_approach}")
        lines.append("")
        lines.append("#### Alternatives Considered")
        lines.append("")
        lines.append("| Option | Description | Pros | Cons |")
        lines.append("|--------|-------------|------|------|")
        for alt in md.alternatives:
            marker = " **(chosen)**" if alt.chosen else ""
            pros = ", ".join(alt.pros) if alt.pros else ""
            cons = ", ".join(alt.cons) if alt.cons else ""
            lines.append(f"| {alt.option_name}{marker} | {alt.description} | {pros} | {cons} |")
        lines.append("")
        lines.append(f"**Chosen:** {md.chosen_alternative}")
        lines.append(f"**Rationale:** {md.rationale}")
        lines.append("")

    lines.extend([
        "---",
        "",
        "## 3. Scaling & Loop Considerations",
        "",
    ])

    for sc in spec.scaling_considerations:
        lines.append(f"### {sc.topic}")
        lines.append(f"- **Current:** {sc.current_approach}")
        lines.append(f"- **Planned:** {sc.planned_approach}")
        if sc.constraints:
            lines.append(f"- **Constraints:** {', '.join(sc.constraints)}")
        if sc.notes:
            lines.append(f"- **Notes:** {sc.notes}")
        lines.append("")

    lines.extend([
        "---",
        "",
        "## 4. Data Model Changes",
        "",
        "| Entity | Source Schema | Target Schema | Changes | Grain Change |",
        "|--------|-------------|---------------|---------|-------------|",
    ])

    for dm in spec.data_model_changes:
        src_s = (
            ", ".join(f"{k}: {v}" for k, v in dm.source_schema.items())
            if dm.source_schema else ""
        )
        tgt_s = (
            ", ".join(f"{k}: {v}" for k, v in dm.target_schema.items())
            if dm.target_schema else ""
        )
        chg = "; ".join(dm.changes) if dm.changes else ""
        lines.append(
            f"| {dm.entity_name} | {src_s} | {tgt_s} | {chg} | {dm.grain_change} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 5. Risks & Mitigations",
        "",
        "| Risk | Severity | Likelihood | Mitigation | Owner |",
        "|------|----------|------------|------------|-------|",
    ])

    for r in spec.risks:
        sev = r.severity.upper()
        lik = r.likelihood.upper()
        lines.append(
            f"| {r.description} | {sev} | {lik} | {r.mitigation} | {r.owner} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 6. Acceptance Criteria",
        "",
    ])

    for c in spec.acceptance_criteria:
        lines.append(f"- [ ] {c}")

    lines.extend([
        "",
        "---",
        "",
        "## Approval",
        "",
    ])

    if spec.approval:
        lines.append(f"- **Approved by:** {spec.approval.approved_by}")
        lines.append(f"- **Date:** {spec.approval.approved_at[:19]}")
        lines.append(f"- **Notes:** {spec.approval.notes}")
    else:
        lines.append("- **Approved by:** _pending_")
        lines.append("- **Date:** _pending_")
        lines.append("- **Notes:** _pending_")

    return "\n".join(lines) + "\n"


def save_spec(
    config: AppConfig,
    increment_id: str,
    spec: ArchitectureSpec,
) -> tuple[Path, Path]:
    """Write spec.md and spec.json to the increment directory."""
    from dataclasses import asdict

    inc_dir = Path(config.project.increments_dir) / increment_id
    ensure_dir(inc_dir)

    md_path = inc_dir / "spec.md"
    md_path.write_text(spec_to_markdown(spec), encoding="utf-8")

    json_path = inc_dir / "spec.json"
    json_path.write_text(
        json.dumps(asdict(spec), indent=2, default=str), encoding="utf-8",
    )

    logger.info("Spec written: %s and %s", md_path, json_path)
    return md_path, json_path


def load_spec_json(config: AppConfig, increment_id: str) -> ArchitectureSpec | None:
    """Load spec from spec.json (machine-readable)."""
    json_path = Path(config.project.increments_dir) / increment_id / "spec.json"
    if not json_path.exists():
        return None

    data = json.loads(json_path.read_text(encoding="utf-8"))
    return _dict_to_spec(data)


def _detect_scaling_considerations(plan) -> list[ScalingConsideration]:
    """Auto-detect scaling topics from construct mappings."""
    considerations = []
    construct_names = " ".join(
        m.source_construct + " " + m.description
        for m in plan.construct_mappings
    ).upper()

    if any(kw in construct_names for kw in ["SYSTASK", "PARALLEL", "BATCH", "WAITFOR"]):
        considerations.append(ScalingConsideration(
            topic="Parallelism",
            current_approach="[Auto-detected: parallel execution pattern in source]",
            planned_approach="[FILL IN: e.g., ProcessPoolExecutor, asyncio, Dask]",
            constraints=["Max concurrent workers", "Memory per worker"],
        ))

    if any(kw in construct_names for kw in ["SORT", "MERGE", "RETAIN", "CHUNK"]):
        considerations.append(ScalingConsideration(
            topic="Memory Management",
            current_approach="[Auto-detected: data sorting/accumulation in source]",
            planned_approach="[FILL IN: streaming, chunked processing, lazy evaluation]",
        ))

    if any(kw in construct_names for kw in ["RETRY", "ERROR", "FAIL"]):
        considerations.append(ScalingConsideration(
            topic="Error Handling & Recovery",
            current_approach="[Auto-detected: retry/error pattern in source]",
            planned_approach="[FILL IN: exception handling, retry decorator, dead letter queue]",
        ))

    if not considerations:
        considerations.append(ScalingConsideration(
            topic="General",
            current_approach="[FILL IN: Current approach]",
            planned_approach="[FILL IN: Planned approach]",
        ))

    return considerations


def _dict_to_spec(d: dict) -> ArchitectureSpec:
    """Reconstruct ArchitectureSpec from a dict."""
    from refactor_framework.models import SpecApproval

    module_decisions = [
        ModuleDecision(
            **{k: v for k, v in md.items() if k != "alternatives"},
            alternatives=[DesignAlternative(**a) for a in md.get("alternatives", [])],
        )
        for md in d.get("module_decisions", [])
    ]

    approval_data = d.get("approval")
    approval = SpecApproval(**approval_data) if approval_data else None

    return ArchitectureSpec(
        increment_id=d.get("increment_id", ""),
        generated_at=d.get("generated_at", ""),
        architecture_overview=d.get("architecture_overview", ""),
        module_decisions=module_decisions,
        scaling_considerations=[
            ScalingConsideration(**sc) for sc in d.get("scaling_considerations", [])
        ],
        data_model_changes=[
            DataModelChange(**dm) for dm in d.get("data_model_changes", [])
        ],
        risks=[RiskItem(**r) for r in d.get("risks", [])],
        acceptance_criteria=d.get("acceptance_criteria", []),
        approval=approval,
    )
