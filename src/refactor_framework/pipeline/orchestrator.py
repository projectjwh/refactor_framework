"""Pipeline orchestrator — chains all steps into a single end-to-end run.

Supports two modes:
  - manual: human has already written the target code and mappings
  - auto: LLM generates code, fills specs, populates mappings
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from refactor_framework.config import AppConfig

logger = logging.getLogger("refactor_framework.pipeline")
console = Console()


def run_pipeline(
    config: AppConfig,
    source_repo: str,
    target_repo: str,
    source_patterns: list[str],
    target_patterns: list[str],
    description: str,
    intake_path: Path,
    mappings_path: Path | None = None,
    mode: str = "manual",
    api_key: str | None = None,
    model: str = "claude-sonnet-4-20250514",
) -> dict:
    """Run the full refactoring pipeline end-to-end.

    Returns a summary dict with status, increment_id, and metrics.
    """
    from refactor_framework.archive.ledger import Ledger
    from refactor_framework.execute.tracker import start_execution, stop_execution
    from refactor_framework.intake.interview import load_intake
    from refactor_framework.mapping.loader import load_mappings, validate_mappings
    from refactor_framework.mapping.scaffold import scaffold_mappings
    from refactor_framework.methodology.generator import generate_methodology
    from refactor_framework.methodology.renderer import render_methodology
    from refactor_framework.pipeline.auto_approve import auto_approve_spec
    from refactor_framework.plan.planner import create_plan, load_plan, save_plan
    from refactor_framework.report.renderer import render_increment_report
    from refactor_framework.snapshot.capture import capture_snapshot
    from refactor_framework.spec.approval import record_approval
    from refactor_framework.spec.generator import generate_spec, load_spec_json, save_spec

    ledger = Ledger(config.archive.ledger_path, config.archive.ledger_backend)
    ai_engine = None

    if mode == "auto":
        from refactor_framework.pipeline.ai_engine import AIEngine

        resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not resolved_key:
            return {"status": "ERROR", "reason": "No API key. Set --api-key or ANTHROPIC_API_KEY."}
        budget = 100000  # default token budget
        intake_data = load_intake(intake_path)
        if intake_data:
            budget = int(intake_data.get("goals", {}).get("budget_usd", 100) / 0.000015)
        ai_engine = AIEngine(resolved_key, model, budget)

    # ── Step 1: Load intake ──────────────────────────────────────────
    _step(1, "Loading intake")
    intake = load_intake(intake_path)
    if not intake:
        return {"status": "ERROR", "reason": f"Intake not found: {intake_path}"}

    # ── Step 2: Create plan ──────────────────────────────────────────
    _step(2, "Creating cross-language plan")
    record = create_plan(
        config,
        file_patterns=target_patterns,
        description=description,
        source_repo=source_repo,
        source_patterns=source_patterns,
        mode="cross-language",
    )
    inc_id = record.increment_id
    ledger.append(record)
    console.print(f"  Increment: [cyan]{inc_id}[/cyan]")

    # ── Step 3: Scaffold source constructs ───────────────────────────
    _step(3, "Scaffolding source constructs")
    scaffold_data = scaffold_mappings(Path(source_repo), source_patterns)
    n_constructs = len(scaffold_data.get("mappings", []))
    console.print(f"  Found {n_constructs} source constructs")

    # ── Step 4: Load or generate mappings ────────────────────────────
    _step(4, f"Loading mappings ({'auto' if mode == 'auto' else 'from file'})")
    if mode == "auto" and ai_engine:
        mappings = ai_engine.map_construct_targets(
            scaffold_data["mappings"], source_repo,
        )
        src_lang = scaffold_data.get("source_language", "")
        tgt_lang = scaffold_data.get("target_language", "")
    else:
        if not mappings_path or not mappings_path.exists():
            return {
                "status": "ERROR",
                "reason": f"Manual mode requires --mappings file. Got: {mappings_path}",
            }
        mappings, src_lang, tgt_lang = load_mappings(mappings_path)

    # Attach mappings to plan
    plan = load_plan(config.project.increments_dir, inc_id)
    from refactor_framework.models import ConstructMapping

    plan.construct_mappings = [
        ConstructMapping(**m) if isinstance(m, dict) else m for m in mappings
    ]
    if src_lang:
        plan.migration.source_language = src_lang
    if tgt_lang:
        plan.migration.target_language = tgt_lang
    save_plan(config.project.increments_dir, inc_id, plan)
    record = ledger.get(inc_id)
    if record:
        record.plan = plan
        ledger.append(record)

    warnings = validate_mappings(
        plan.construct_mappings, plan.source_files, plan.target_files,
    )
    for w in warnings:
        console.print(f"  [yellow]WARNING: {w}[/yellow]")
    console.print(f"  Attached {len(plan.construct_mappings)} mappings")

    # ── Step 5: Generate spec ────────────────────────────────────────
    _step(5, "Generating architecture spec")
    spec = generate_spec(config, inc_id)

    if mode == "auto" and ai_engine:
        spec = ai_engine.fill_spec_placeholders(spec, plan, intake)

    save_spec(config, inc_id, spec)
    record = ledger.get(inc_id)
    if record:
        record.status = "spec_generated"
        record.spec = spec
        ledger.append(record)
    console.print(
        f"  {len(spec.module_decisions)} module decisions, "
        f"{len(spec.risks)} risks"
    )

    # ── Step 6: Approve ──────────────────────────────────────────────
    _step(6, "Approving spec")
    if mode == "auto":
        approved, reason = auto_approve_spec(spec, intake)
        if not approved:
            console.print(f"  [red]{reason}[/red]")
            # In auto mode with placeholders, approve anyway with note
            record_approval(
                config, inc_id, "pipeline-auto",
                f"Auto-approved with caveats: {reason}",
            )
        else:
            record_approval(config, inc_id, "pipeline-auto", reason)
            console.print(f"  [green]{reason}[/green]")
    else:
        record_approval(
            config, inc_id, "pipeline-manual",
            "Pre-approved via manual pipeline (mappings provided by user)",
        )
        console.print("  Pre-approved (manual mode)")

    record = ledger.get(inc_id)
    if record:
        record.status = "spec_approved"
        spec = load_spec_json(config, inc_id)
        if spec:
            record.spec = spec
        ledger.append(record)

    # ── Step 7: Snapshot before ──────────────────────────────────────
    _step(7, "Capturing before snapshot")
    before = capture_snapshot(config, inc_id, "before")
    record = ledger.get(inc_id)
    if record:
        record.before = before
        record.status = "snapshot_before"
        ledger.append(record)
    console.print(f"  {len(before.files)} files, {before.total_loc} LOC")

    # ── Step 8: Execute ──────────────────────────────────────────────
    _step(8, f"Executing ({'AI generating code' if mode == 'auto' else 'code already written'})")
    start_execution(config, inc_id)

    tokens_in = tokens_out = 0
    if mode == "auto" and ai_engine:
        target_dir = Path(target_repo)
        target_dir.mkdir(parents=True, exist_ok=True)
        for src_file in plan.source_files:
            code = ai_engine.generate_refactored_code(
                Path(source_repo) / src_file,
                tgt_lang or "Python",
                spec,
            )
            # Determine target filename
            tgt_name = Path(src_file).stem + ".py"
            (target_dir / tgt_name).write_text(code, encoding="utf-8")
            console.print(f"  Generated: {tgt_name}")
        tokens_in = ai_engine.tokens_used_input
        tokens_out = ai_engine.tokens_used_output

    time_rec, token_usage = stop_execution(
        config, inc_id,
        tokens_input=tokens_in,
        tokens_output=tokens_out,
        model=model,
    )
    record = ledger.get(inc_id)
    if record:
        record.time_record = time_rec
        record.token_usage = token_usage
        ledger.append(record)
    console.print(
        f"  {time_rec.duration_seconds:.1f}s, "
        f"{token_usage.total_tokens:,} tokens, "
        f"${token_usage.cost_estimate_usd:.4f}"
    )

    # ── Step 9: Snapshot after ───────────────────────────────────────
    _step(9, "Capturing after snapshot")
    after = capture_snapshot(config, inc_id, "after")
    record = ledger.get(inc_id)
    if record:
        record.after = after
        record.status = "snapshot_after"
        record.efficiency.loc_delta = after.total_loc - before.total_loc
        record.efficiency.complexity_delta = (
            after.avg_complexity - before.avg_complexity
        )
        record.efficiency.maintainability_delta = (
            after.avg_maintainability - before.avg_maintainability
        )
        ledger.append(record)
    console.print(f"  {len(after.files)} files, {after.total_loc} LOC")

    # ── Step 10: Report ──────────────────────────────────────────────
    _step(10, "Generating migration report")
    record = ledger.get(inc_id)
    if record:
        record.plan = load_plan(config.project.increments_dir, inc_id)
        record.status = "reported"
        ledger.append(record)

    inc_dir = Path(config.project.increments_dir) / inc_id
    report_path = inc_dir / "report.html"
    render_increment_report(
        record, [], report_path, config.report.template_dir,
        plan=record.plan, increment_dir=inc_dir,
    )
    console.print(f"  {report_path}")

    # ── Step 11: Methodology ─────────────────────────────────────────
    _step(11, "Generating methodology document")
    spec = load_spec_json(config, inc_id)
    if spec and record:
        methodology = generate_methodology(record, spec)
        meth_path = inc_dir / "methodology.html"
        render_methodology(record, methodology, meth_path)
        record.status = "methodology"
        record.methodology = methodology
        ledger.append(record)
        console.print(f"  {meth_path}")

    # ── Summary ──────────────────────────────────────────────────────
    summary = {
        "status": "COMPLETE",
        "increment_id": inc_id,
        "mode": mode,
        "source_loc": before.total_loc,
        "target_loc": after.total_loc,
        "loc_delta": after.total_loc - before.total_loc,
        "tokens": token_usage.total_tokens,
        "cost_usd": token_usage.cost_estimate_usd,
        "constructs_mapped": len(plan.construct_mappings),
        "risks_identified": len(spec.risks) if spec else 0,
    }

    console.print()
    console.print(Panel(
        f"[bold green]Pipeline complete![/bold green]\n\n"
        f"Increment: {inc_id}\n"
        f"LOC: {before.total_loc} -> {after.total_loc} "
        f"({after.total_loc - before.total_loc:+d})\n"
        f"Tokens: {token_usage.total_tokens:,} | "
        f"Cost: ${token_usage.cost_estimate_usd:.4f}\n"
        f"Constructs: {len(plan.construct_mappings)} mapped\n\n"
        f"Artifacts:\n"
        f"  spec.md          -> {inc_dir / 'spec.md'}\n"
        f"  report.html      -> {report_path}\n"
        f"  methodology.html -> {inc_dir / 'methodology.html'}",
        border_style="green",
        title="Pipeline Summary",
    ))

    return summary


def _step(n: int, label: str) -> None:
    """Print a step header."""
    console.print(f"\n[bold blue]Step {n:2d}[/bold blue] {label}")
