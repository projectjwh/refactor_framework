"""CLI entry point for Refactor Framework.

Usage:
    python -m refactor_framework <command> [options]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from refactor_framework import __version__


def _add_config_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config", type=str, default=None,
        help="Path to YAML config file (default: config/default.yaml)",
    )


def _add_increment_id_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--increment-id", type=str, required=True,
        help="Increment identifier (e.g., 20260326T143022)",
    )


def _check_increment_id(args) -> bool:
    """Validate increment ID format. Returns True if valid, prints error if not."""
    from refactor_framework.utils.ids import validate_increment_id

    inc_id = getattr(args, "increment_id", None)
    if inc_id and not validate_increment_id(inc_id):
        print(
            f"Error: invalid increment ID '{inc_id}'. "
            f"Expected format: YYYYMMDDTHHMMSS (e.g., 20260326T143022).\n"
            f"  Run 'status' to see valid increment IDs.",
            file=sys.stderr,
        )
        return False
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="refactor_framework",
        description="Refactor Framework — systematic legacy code refactoring with metrics tracking",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    sub = parser.add_subparsers(dest="command", help="Available commands")

    # -- init --
    init_p = sub.add_parser("init", help="Initialize a refactoring project")
    init_p.add_argument("--target-repo", type=str, required=True, help="Path to target codebase")
    init_p.add_argument("--name", type=str, default="", help="Project name")
    _add_config_arg(init_p)

    # -- intake --
    intake_p = sub.add_parser("intake", help="Run structured intake interview")
    _add_config_arg(intake_p)

    # -- plan --
    plan_p = sub.add_parser("plan", help="Create an increment plan")
    plan_p.add_argument("--files", nargs="+", required=True, help="File glob patterns")
    plan_p.add_argument("--description", type=str, required=True, help="What this increment does")
    plan_p.add_argument("--criteria", nargs="*", default=[], help="Acceptance criteria")
    plan_p.add_argument("--patterns", nargs="*", default=[], help="Target refactoring patterns")
    plan_p.add_argument(
        "--source-repo", type=str, default=None, help="Path to source codebase",
    )
    plan_p.add_argument("--source-files", nargs="*", default=[], help="Source file glob patterns")
    plan_p.add_argument(
        "--mode", type=str, default="same-language",
        choices=["same-language", "cross-language"], help="Migration mode",
    )
    _add_config_arg(plan_p)

    # -- map --
    map_p = sub.add_parser("map", help="Attach construct mappings to an increment")
    _add_increment_id_arg(map_p)
    map_p.add_argument("--mappings-file", type=str, required=True, help="Path to mappings YAML")
    _add_config_arg(map_p)

    # -- snapshot --
    snap_p = sub.add_parser("snapshot", help="Capture file snapshot and metrics")
    _add_increment_id_arg(snap_p)
    snap_p.add_argument("--phase", type=str, required=True, choices=["before", "after"])
    _add_config_arg(snap_p)

    # -- execute --
    exec_p = sub.add_parser("execute", help="Track execution time and tokens")
    _add_increment_id_arg(exec_p)
    exec_p.add_argument("--action", type=str, required=True, choices=["start", "stop"])
    exec_p.add_argument("--tokens-input", type=int, default=0, help="Input tokens used")
    exec_p.add_argument("--tokens-output", type=int, default=0, help="Output tokens used")
    exec_p.add_argument("--tokens-total", type=int, default=0, help="Total tokens (splits 60/40)")
    exec_p.add_argument("--model", type=str, default=None, help="Model name")
    exec_p.add_argument("--cost-input", type=float, default=None, help="Cost per input token")
    exec_p.add_argument("--cost-output", type=float, default=None, help="Cost per output token")
    _add_config_arg(exec_p)

    # -- scaffold --
    scaff_p = sub.add_parser("scaffold", help="Auto-generate mapping YAML from source files")
    scaff_p.add_argument("--source-dir", type=str, required=True, help="Source codebase")
    scaff_p.add_argument("--patterns", nargs="+", required=True, help="File patterns")
    scaff_p.add_argument("--output", type=str, required=True, help="Output YAML path")
    scaff_p.add_argument("--target-lang", type=str, default="Python", help="Target language")
    _add_config_arg(scaff_p)

    # -- validate --
    val_p = sub.add_parser("validate", help="Compare source vs target data outputs")
    val_p.add_argument("--source-output", type=str, required=True, help="Source data file")
    val_p.add_argument("--target-output", type=str, required=True, help="Target data file")
    val_p.add_argument("--key", type=str, required=True, help="Comma-separated key columns")
    val_p.add_argument("--tolerance", type=float, default=0.0, help="Numeric tolerance")
    val_p.add_argument("--report", type=str, default=None, help="Output report JSON path")
    _add_config_arg(val_p)

    # -- spec --
    spec_p = sub.add_parser("spec", help="Generate architecture spec for review")
    _add_increment_id_arg(spec_p)
    _add_config_arg(spec_p)

    # -- approve --
    appr_p = sub.add_parser("approve", help="Approve architecture spec")
    _add_increment_id_arg(appr_p)
    appr_p.add_argument("--approved-by", type=str, required=True, help="Reviewer name")
    appr_p.add_argument("--notes", type=str, default="", help="Approval notes")
    _add_config_arg(appr_p)

    # -- methodology --
    meth_p = sub.add_parser("methodology", help="Generate methodology document")
    _add_increment_id_arg(meth_p)
    _add_config_arg(meth_p)

    # -- next --
    next_p = sub.add_parser("next", help="Show next step for latest increment")
    _add_config_arg(next_p)

    # -- coverage --
    cov_p = sub.add_parser("coverage", help="Show cross-increment source coverage")
    cov_p.add_argument("--format", type=str, default="table", choices=["table", "json"])
    _add_config_arg(cov_p)

    # -- burndown --
    burn_p = sub.add_parser("burndown", help="Show velocity and burndown metrics")
    burn_p.add_argument("--format", type=str, default="table", choices=["table", "json"])
    _add_config_arg(burn_p)

    # -- test --
    test_p = sub.add_parser("test", help="Run tests and record results")
    _add_increment_id_arg(test_p)
    test_p.add_argument("--phase", type=str, required=True, choices=["before", "after"])
    test_p.add_argument("--command", type=str, default=None, help="Test command to run")
    _add_config_arg(test_p)

    # -- report --
    report_p = sub.add_parser("report", help="Generate HTML report")
    report_p.add_argument("--increment-id", type=str, default=None, help="Single increment")
    report_p.add_argument("--all", action="store_true", help="Generate aggregate dashboard")
    _add_config_arg(report_p)

    # -- reset --
    reset_p = sub.add_parser("reset", help="Reset increment to earlier status")
    _add_increment_id_arg(reset_p)
    reset_p.add_argument(
        "--to-status", type=str, default="planned",
        choices=["planned", "spec_generated", "spec_approved"],
        help="Status to reset to",
    )
    _add_config_arg(reset_p)

    # -- status --
    status_p = sub.add_parser("status", help="Show all increments status")
    status_p.add_argument(
        "--format", type=str, default="table", choices=["table", "json"],
    )
    _add_config_arg(status_p)

    # -- history --
    history_p = sub.add_parser("history", help="Show increment history")
    history_p.add_argument("--format", type=str, default="table", choices=["table", "json"])
    _add_config_arg(history_p)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    from refactor_framework.config import load_config
    from refactor_framework.utils.logging import setup_logging

    setup_logging()
    config = load_config(args.config)

    # Validate increment-id if present, enable per-increment logging
    if hasattr(args, "increment_id") and args.increment_id:
        if not _check_increment_id(args):
            return 1
        from refactor_framework.utils.logging import setup_increment_logging

        setup_increment_logging(args.increment_id, config.project.increments_dir)

    dispatch = {
        "init": _cmd_init, "intake": _cmd_intake,
        "plan": _cmd_plan, "map": _cmd_map,
        "spec": _cmd_spec, "approve": _cmd_approve,
        "snapshot": _cmd_snapshot, "execute": _cmd_execute, "test": _cmd_test,
        "report": _cmd_report, "methodology": _cmd_methodology,
        "reset": _cmd_reset, "status": _cmd_status, "history": _cmd_history,
        "scaffold": _cmd_scaffold, "validate": _cmd_validate, "next": _cmd_next,
        "coverage": _cmd_coverage, "burndown": _cmd_burndown,
    }
    handler = dispatch.get(args.command)
    if handler:
        return handler(config, args)

    parser.print_help()
    return 1


# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------


def _cmd_init(config, args) -> int:
    import yaml

    from refactor_framework.config import find_project_root
    from refactor_framework.utils.paths import ensure_dir

    root = find_project_root()
    target = Path(args.target_repo).resolve()

    if not target.is_dir():
        print(f"Error: target repo not found: {target}", file=sys.stderr)
        return 1

    # Update config file with target repo
    config_path = root / "config" / "default.yaml"
    if config_path.exists():
        data = yaml.safe_load(config_path.read_text()) or {}
    else:
        data = {}

    data.setdefault("project", {})
    data["project"]["target_repo"] = str(target)
    if args.name:
        data["project"]["name"] = args.name

    ensure_dir(config_path.parent)
    config_path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))

    # Create directories
    ensure_dir(root / data.get("project", {}).get("increments_dir", "increments"))
    ensure_dir(root / data.get("project", {}).get("output_dir", "output"))
    ensure_dir(root / data.get("project", {}).get("devlogs_dir", "devlogs"))

    # Initialize empty ledger
    ledger_path = root / data.get("archive", {}).get("ledger_path", "output/ledger.json")
    ensure_dir(ledger_path.parent)
    if not ledger_path.exists():
        ledger_path.write_text("[]")

    print(f"Initialized refactoring project targeting: {target}")
    print(f"Config: {config_path}")
    print("  Next: python -m refactor_framework intake")
    return 0


def _cmd_intake(config, args) -> int:
    from refactor_framework.config import find_project_root
    from refactor_framework.intake.interview import run_intake

    root = find_project_root()
    output = root / "intake.yaml"
    run_intake(output)
    return 0


def _cmd_plan(config, args) -> int:
    from refactor_framework.archive.ledger import Ledger
    from refactor_framework.plan.planner import create_plan

    # Auto-detect cross-language mode if source-repo is provided
    mode = args.mode
    if args.source_repo and mode == "same-language":
        mode = "cross-language"

    record = create_plan(
        config,
        file_patterns=args.files,
        description=args.description,
        criteria=args.criteria,
        target_patterns=args.patterns,
        source_repo=args.source_repo,
        source_patterns=args.source_files if args.source_files else None,
        mode=mode,
    )

    ledger = Ledger(config.archive.ledger_path, config.archive.ledger_backend)
    ledger.append(record)

    print(f"Created increment: {record.increment_id}")
    print(f"  Mode: {mode}")
    print(f"  Target files: {len(record.plan.target_files)}")
    if record.plan.source_files:
        print(f"  Source files: {len(record.plan.source_files)}")
    print(f"  Description: {record.plan.description}")
    return 0


def _cmd_map(config, args) -> int:
    from pathlib import Path

    from refactor_framework.archive.ledger import Ledger
    from refactor_framework.mapping.loader import load_mappings, validate_mappings
    from refactor_framework.plan.planner import load_plan, save_plan

    plan = load_plan(config.project.increments_dir, args.increment_id)
    mappings, src_lang, tgt_lang = load_mappings(Path(args.mappings_file))

    # Update plan with mappings
    plan.construct_mappings = mappings
    if src_lang:
        plan.migration.source_language = src_lang
    if tgt_lang:
        plan.migration.target_language = tgt_lang

    # Validate
    warnings = validate_mappings(mappings, plan.source_files, plan.target_files)
    for w in warnings:
        print(f"  WARNING: {w}")

    # Save updated plan
    save_plan(config.project.increments_dir, args.increment_id, plan)

    # Update ledger
    ledger = Ledger(config.archive.ledger_path, config.archive.ledger_backend)
    record = ledger.get(args.increment_id)
    if record:
        record.plan = plan
        ledger.append(record)

    from refactor_framework.mapping.loader import compute_coverage

    cov = compute_coverage(mappings)
    print(f"Attached {len(mappings)} construct mappings to {args.increment_id}")
    print(f"  Coverage: {cov['complete']}/{cov['total']} complete ({cov['pct_complete']}%)")
    return 0


def _cmd_snapshot(config, args) -> int:
    from refactor_framework.archive.ledger import Ledger
    from refactor_framework.snapshot.capture import capture_snapshot
    from refactor_framework.spec.approval import check_approval, has_spec

    # Gate: if spec exists but not approved, block before-snapshot
    if args.phase == "before" and has_spec(config, args.increment_id):
        if not check_approval(config, args.increment_id):
            print("Error: spec exists but is not approved.", file=sys.stderr)
            print(f"  Review increments/{args.increment_id}/spec.md then run:")
            print(f"  approve --increment-id {args.increment_id} --approved-by <name>")
            return 1

    snapshot = capture_snapshot(config, args.increment_id, args.phase)

    # Update ledger
    ledger = Ledger(config.archive.ledger_path, config.archive.ledger_backend)
    record = ledger.get(args.increment_id)
    if record:
        if args.phase == "before":
            record.before = snapshot
            record.status = "snapshot_before"
        else:
            record.after = snapshot
            record.status = "snapshot_after"
            # Compute efficiency deltas if both snapshots exist
            if record.before:
                record.efficiency.loc_delta = snapshot.total_loc - record.before.total_loc
                record.efficiency.complexity_delta = (
                    snapshot.avg_complexity - record.before.avg_complexity
                )
                record.efficiency.maintainability_delta = (
                    snapshot.avg_maintainability - record.before.avg_maintainability
                )
        ledger.append(record)

    print(f"Captured {args.phase} snapshot: {len(snapshot.files)} files, {snapshot.total_loc} LOC")
    return 0


def _cmd_execute(config, args) -> int:
    from refactor_framework.archive.ledger import Ledger
    from refactor_framework.execute.tracker import start_execution, stop_execution

    if args.action == "start":
        ts = start_execution(config, args.increment_id)

        ledger = Ledger(config.archive.ledger_path, config.archive.ledger_backend)
        record = ledger.get(args.increment_id)
        if record:
            record.status = "executing"
            ledger.append(record)

        print(f"Execution started at {ts}")
    else:
        # --tokens-total shorthand: split 60/40 (typical LLM input/output ratio)
        t_in = args.tokens_input
        t_out = args.tokens_output
        if args.tokens_total > 0 and t_in == 0 and t_out == 0:
            t_in = int(args.tokens_total * 0.6)
            t_out = args.tokens_total - t_in

        time_rec, token_usage = stop_execution(
            config, args.increment_id,
            tokens_input=t_in,
            tokens_output=t_out,
            model=args.model,
            cost_per_input=args.cost_input,
            cost_per_output=args.cost_output,
        )

        ledger = Ledger(config.archive.ledger_path, config.archive.ledger_backend)
        record = ledger.get(args.increment_id)
        if record:
            record.time_record = time_rec
            record.token_usage = token_usage
            # Compute token efficiency if we have LOC delta
            if record.token_usage.total_tokens > 0 and record.efficiency.loc_delta != 0:
                record.efficiency.lines_changed_per_token = (
                    abs(record.efficiency.loc_delta) / record.token_usage.total_tokens
                )
            if record.time_record.duration_seconds > 0 and record.efficiency.complexity_delta != 0:
                hours = record.time_record.duration_seconds / 3600.0
                record.efficiency.complexity_delta_per_hour = (
                    abs(record.efficiency.complexity_delta) / hours
                )
            ledger.append(record)

        print(f"Execution stopped: {time_rec.duration_seconds:.1f}s, "
              f"{token_usage.total_tokens:,} tokens, ${token_usage.cost_estimate_usd:.4f}")
    return 0


def _cmd_test(config, args) -> int:
    from refactor_framework.archive.ledger import Ledger
    from refactor_framework.test.runner import run_tests

    result = run_tests(config, args.increment_id, args.phase, command=args.command)

    ledger = Ledger(config.archive.ledger_path, config.archive.ledger_backend)
    record = ledger.get(args.increment_id)
    if record:
        if args.phase == "before":
            record.test_before = result
        else:
            record.test_after = result
            record.status = "tested"
        ledger.append(record)

    print(f"Tests ({args.phase}): {result.passed} passed, {result.failed} failed, "
          f"{result.errors} errors, {result.skipped} skipped ({result.duration_seconds:.1f}s)")
    return 0


def _cmd_report(config, args) -> int:
    from refactor_framework.archive.ledger import Ledger
    from refactor_framework.plan.planner import load_plan
    from refactor_framework.report.diff import generate_all_diffs
    from refactor_framework.report.renderer import render_dashboard, render_increment_report

    ledger = Ledger(config.archive.ledger_path, config.archive.ledger_backend)

    if args.all:
        records = ledger.list_all()
        output = Path(config.project.output_dir) / "dashboard.html"
        render_dashboard(records, output, config.report.template_dir)
        print(f"Dashboard written: {output}")
        return 0

    if not args.increment_id:
        print("Error: provide --increment-id or --all", file=sys.stderr)
        return 1

    record = ledger.get(args.increment_id)
    if not record:
        print(
            f"Error: increment {args.increment_id} not found in ledger.\n"
            f"  Run 'status' to see valid IDs.",
            file=sys.stderr,
        )
        return 1

    inc_dir = Path(config.project.increments_dir) / args.increment_id
    plan = load_plan(config.project.increments_dir, args.increment_id)

    # Sync construct_mappings from plan into record
    record.plan = plan
    record.status = "reported"

    is_cross = plan.migration.mode == "cross-language" and plan.construct_mappings
    if is_cross:
        diffs = []
    else:
        diffs = generate_all_diffs(inc_dir, plan.target_files, config.report.diff_style)
        record.diff_summary = {
            d["rel_path"]: {"added": d["added"], "removed": d["removed"]}
            for d in diffs if d["changed"]
        }

    ledger.append(record)

    output = inc_dir / "report.html"
    render_increment_report(
        record, diffs, output, config.report.template_dir,
        plan=plan, increment_dir=inc_dir,
    )
    mode_label = "Migration report" if is_cross else "Report"
    print(f"{mode_label} written: {output}")
    return 0


def _cmd_status(config, args) -> int:
    from refactor_framework.archive.ledger import Ledger

    ledger = Ledger(config.archive.ledger_path, config.archive.ledger_backend)
    records = ledger.list_all()

    if not records:
        print("No increments found.")
        return 0

    if getattr(args, "format", "table") == "json":
        data = [
            {
                "increment_id": r.increment_id,
                "status": r.status,
                "description": r.plan.description,
                "files": len(r.plan.target_files),
                "loc_delta": r.efficiency.loc_delta,
                "cc_delta": r.efficiency.complexity_delta,
                "tokens": r.token_usage.total_tokens,
                "cost": r.token_usage.cost_estimate_usd,
            }
            for r in records
        ]
        print(json.dumps(data, indent=2))
        return 0

    from rich.console import Console
    from rich.table import Table

    table = Table(title="Refactoring Increments")
    table.add_column("ID", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Description")
    table.add_column("Files", justify="right")
    table.add_column("LOC Delta", justify="right")
    table.add_column("CC Delta", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("Cost", justify="right")

    for r in records:
        loc_d = r.efficiency.loc_delta
        cc_d = r.efficiency.complexity_delta
        loc_style = "green" if loc_d < 0 else "red" if loc_d > 0 else ""
        cc_style = "green" if cc_d < 0 else "red" if cc_d > 0 else ""

        table.add_row(
            r.increment_id,
            r.status,
            r.plan.description[:40],
            str(len(r.plan.target_files)),
            f"[{loc_style}]{loc_d:+d}[/{loc_style}]" if loc_style else str(loc_d),
            f"[{cc_style}]{cc_d:+.2f}[/{cc_style}]" if cc_style else f"{cc_d:.2f}",
            f"{r.token_usage.total_tokens:,}",
            f"${r.token_usage.cost_estimate_usd:.4f}",
        )

    Console().print(table)
    return 0


def _cmd_history(config, args) -> int:
    from refactor_framework.archive.ledger import Ledger
    from refactor_framework.report.dashboard import compute_dashboard_data

    ledger = Ledger(config.archive.ledger_path, config.archive.ledger_backend)
    records = ledger.list_all()

    if not records:
        print("No increments found.")
        return 0

    data = compute_dashboard_data(records)

    if args.format == "json":
        print(json.dumps(data, indent=2))
    else:
        from rich.console import Console
        from rich.table import Table

        console = Console()

        # Summary
        s = data["summary"]
        console.print(f"\n[bold]Summary[/bold]: {s['total_increments']} increments, "
                       f"{s['total_loc_delta']:+d} LOC, {s['total_cc_delta']:+.2f} CC, "
                       f"{s['total_tokens']:,} tokens, ${s['total_cost']:.2f}")

        e = data["efficiency"]
        console.print(
            f"[bold]Efficiency[/bold]: {e['lines_per_1k_tokens']} lines/1K tokens, "
            f"{e['cc_per_hour']} CC/hour, ${e['avg_cost_per_increment']:.4f}/increment\n"
        )

        table = Table(title="Increment History")
        table.add_column("ID", style="cyan")
        table.add_column("Date")
        table.add_column("Description")
        table.add_column("LOC Delta", justify="right")
        table.add_column("CC Delta", justify="right")
        table.add_column("Tokens", justify="right")
        table.add_column("Hours", justify="right")

        for inc in data["increments"]:
            table.add_row(
                inc["increment_id"],
                inc["date"],
                inc["description"][:35],
                f"{inc['loc_delta']:+d}",
                f"{inc['cc_delta']:+.2f}",
                f"{inc['tokens']:,}",
                f"{inc['duration_hours']:.1f}",
            )

        console.print(table)

    return 0


def _cmd_reset(config, args) -> int:
    import shutil

    from refactor_framework.archive.ledger import Ledger

    ledger = Ledger(config.archive.ledger_path, config.archive.ledger_backend)
    record = ledger.get(args.increment_id)
    if not record:
        print(
            f"Error: increment {args.increment_id} not found.\n"
            f"  Run 'status' to see valid IDs.",
            file=sys.stderr,
        )
        return 1

    inc_dir = Path(config.project.increments_dir) / args.increment_id
    target = args.to_status

    # Clean artifacts that belong to later phases
    artifacts_to_clean = {
        "planned": ["spec.md", "spec.json", "before", "after",
                     "before_metrics.json", "after_metrics.json",
                     "execution_start.json", "execution_end.json",
                     "report.html", "methodology.html"],
        "spec_generated": ["before", "after", "before_metrics.json",
                           "after_metrics.json", "execution_start.json",
                           "execution_end.json", "report.html",
                           "methodology.html"],
        "spec_approved": ["before", "after", "before_metrics.json",
                          "after_metrics.json", "execution_start.json",
                          "execution_end.json", "report.html",
                          "methodology.html"],
    }

    for artifact in artifacts_to_clean.get(target, []):
        p = inc_dir / artifact
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()

    record.status = target
    if target == "planned":
        record.spec = None
        record.before = None
        record.after = None
        record.methodology = None
    ledger.append(record)

    print(f"Increment {args.increment_id} reset to '{target}'")
    return 0


def _cmd_spec(config, args) -> int:
    from refactor_framework.archive.ledger import Ledger
    from refactor_framework.spec.generator import generate_spec, save_spec

    spec = generate_spec(config, args.increment_id)
    md_path, json_path = save_spec(config, args.increment_id, spec)

    # Update ledger
    ledger = Ledger(config.archive.ledger_path, config.archive.ledger_backend)
    record = ledger.get(args.increment_id)
    if record:
        record.status = "spec_generated"
        record.spec = spec
        ledger.append(record)

    n_modules = len(spec.module_decisions)
    n_risks = len(spec.risks)
    print(f"Architecture spec generated: {md_path}")
    print(f"  {n_modules} module decisions, {n_risks} risks identified")
    print("  Review and edit spec.md, then run:")
    print(f"  approve --increment-id {args.increment_id} --approved-by <your-name>")
    return 0


def _cmd_approve(config, args) -> int:
    from refactor_framework.archive.ledger import Ledger
    from refactor_framework.spec.approval import record_approval
    from refactor_framework.spec.generator import load_spec_json

    approval = record_approval(
        config, args.increment_id, args.approved_by, args.notes,
    )

    # Update ledger
    ledger = Ledger(config.archive.ledger_path, config.archive.ledger_backend)
    record = ledger.get(args.increment_id)
    if record:
        record.status = "spec_approved"
        spec = load_spec_json(config, args.increment_id)
        if spec:
            record.spec = spec
        ledger.append(record)

    print(f"Spec approved by {approval.approved_by} at {approval.approved_at[:19]}")
    print(f"  Next: snapshot --increment-id {args.increment_id} --phase before")
    return 0


def _cmd_methodology(config, args) -> int:
    from refactor_framework.archive.ledger import Ledger
    from refactor_framework.methodology.generator import generate_methodology
    from refactor_framework.methodology.renderer import render_methodology
    from refactor_framework.spec.generator import load_spec_json

    ledger = Ledger(config.archive.ledger_path, config.archive.ledger_backend)
    record = ledger.get(args.increment_id)
    if not record:
        print(
            f"Error: increment {args.increment_id} not found.\n"
            f"  Run 'status' to see valid IDs.",
            file=sys.stderr,
        )
        return 1

    spec = load_spec_json(config, args.increment_id)
    if not spec:
        print(
            f"Error: no spec found for {args.increment_id}.\n"
            f"  Run: spec --increment-id {args.increment_id}",
            file=sys.stderr,
        )
        return 1

    methodology = generate_methodology(record, spec)
    inc_dir = Path(config.project.increments_dir) / args.increment_id
    output = inc_dir / "methodology.html"
    render_methodology(record, methodology, output)

    record.status = "methodology"
    record.methodology = methodology
    ledger.append(record)

    print(f"Methodology document written: {output}")
    return 0


def _cmd_scaffold(config, args) -> int:
    from refactor_framework.mapping.scaffold import scaffold_to_file

    count = scaffold_to_file(
        Path(args.source_dir), args.patterns, Path(args.output), args.target_lang,
    )
    print(f"Scaffolded {count} construct mappings -> {args.output}")
    print("Edit the YAML to fill in target_file/target_construct, then run 'map'.")
    return 0


def _cmd_validate(config, args) -> int:
    from refactor_framework.validate.equivalence import compare_outputs, compare_to_report

    result = compare_outputs(
        Path(args.source_output), Path(args.target_output),
        key_columns=args.key.split(","), tolerance=args.tolerance,
    )

    if args.report:
        compare_to_report(result, Path(args.report))

    # Print summary
    match_str = "[green]MATCH[/green]" if result["match"] else "[red]MISMATCH[/red]"
    from rich.console import Console
    console = Console()
    console.print(f"\n  {match_str}: {result['summary']}")
    console.print(f"  Source: {result['source_rows']} rows | Target: {result['target_rows']} rows")
    if result["row_diffs"]:
        console.print(f"  Sample diffs ({len(result['row_diffs'])}):")
        for d in result["row_diffs"][:5]:
            console.print(
                f"    {d['key']} | {d['column']}: "
                f"{d['source_value']!r} -> {d['target_value']!r}"
            )
    return 0 if result["match"] else 1


def _cmd_next(config, args) -> int:
    from refactor_framework.archive.ledger import Ledger

    ledger = Ledger(config.archive.ledger_path, config.archive.ledger_backend)
    records = ledger.list_all()

    if not records:
        from refactor_framework.config import find_project_root

        intake_path = find_project_root() / "intake.yaml"
        if not intake_path.exists():
            print("No intake completed. Run: intake")
        else:
            print("Intake done. Run: plan --files ... --description ...")
        return 0

    latest = records[-1]
    status = latest.status
    inc_id = latest.increment_id

    workflow = {
        "planned": f"spec --increment-id {inc_id}",
        "spec_generated": (
            f"Review/edit increments/{inc_id}/spec.md, then:\n"
            f"  approve --increment-id {inc_id} --approved-by <your-name>"
        ),
        "spec_approved": f"snapshot --increment-id {inc_id} --phase before",
        "snapshot_before": f"execute --increment-id {inc_id} --action start",
        "executing": f"execute --increment-id {inc_id} --action stop --tokens-total <N>",
        "snapshot_after": f"report --increment-id {inc_id}",
        "tested": f"report --increment-id {inc_id}",
        "reported": f"methodology --increment-id {inc_id}",
        "methodology": "plan --files ... --description '...'  (start next increment)",
    }

    # Special: after start, remind to do the actual work then stop+snapshot
    if status == "executing":
        print(f"Increment {inc_id} is executing. When done refactoring:")
        print(f"  1. python -m refactor_framework execute"
              f" --increment-id {inc_id} --action stop --tokens-total <N>")
        print(f"  2. python -m refactor_framework snapshot"
              f" --increment-id {inc_id} --phase after")
        return 0

    next_cmd = workflow.get(status)
    if next_cmd:
        print(f"Increment {inc_id} ({status}). Next step:")
        print(f"  python -m refactor_framework {next_cmd}")
    else:
        print(f"Increment {inc_id} status: {status}")

    return 0


def _cmd_coverage(config, args) -> int:
    from refactor_framework.archive.ledger import Ledger
    from refactor_framework.mapping.coverage import compute_source_coverage

    ledger = Ledger(config.archive.ledger_path, config.archive.ledger_backend)
    records = ledger.list_all()
    data = compute_source_coverage(records)

    if args.format == "json":
        print(json.dumps(data, indent=2))
        return 0

    from rich.console import Console
    from rich.table import Table

    console = Console()
    t = data["totals"]
    console.print(
        f"\n[bold]Source Coverage[/bold]: {t['complete']}/{t['constructs']} "
        f"constructs complete ({t['pct_complete']}%)\n"
    )

    table = Table(title="Coverage by Source File")
    table.add_column("Source File")
    table.add_column("Total", justify="right")
    table.add_column("Complete", justify="right", style="green")
    table.add_column("Partial", justify="right", style="yellow")
    table.add_column("TODO", justify="right", style="red")
    table.add_column("Coverage", justify="right")

    for sf in data["source_files"]:
        table.add_row(
            sf["file"], str(sf["total_constructs"]),
            str(sf["complete"]), str(sf["partial"]),
            str(sf["todo"]), f"{sf['pct']}%",
        )
    console.print(table)

    if data["unmapped_constructs"]:
        n_unmapped = len(data["unmapped_constructs"])
        console.print(f"\n[bold red]Unmapped constructs ({n_unmapped}):[/bold red]")
        for u in data["unmapped_constructs"][:10]:
            console.print(f"  {u['source_file']}::{u['construct']}")
        if len(data["unmapped_constructs"]) > 10:
            console.print(f"  ... and {len(data['unmapped_constructs']) - 10} more")

    return 0


def _cmd_burndown(config, args) -> int:
    from refactor_framework.archive.ledger import Ledger
    from refactor_framework.mapping.coverage import compute_burndown

    ledger = Ledger(config.archive.ledger_path, config.archive.ledger_backend)
    records = ledger.list_all()
    data = compute_burndown(records)

    if args.format == "json":
        print(json.dumps(data, indent=2))
        return 0

    from rich.console import Console
    from rich.table import Table

    console = Console()
    v = data["velocity"]
    b = data["burndown"]

    console.print("\n[bold]Velocity[/bold]")
    console.print(f"  Avg LOC/increment:       {v['avg_loc_per_increment']}")
    console.print(f"  Avg cost/increment:      ${v['avg_cost_per_increment']}")
    console.print(f"  Avg cost/LOC:            ${v['avg_cost_per_loc']}")
    console.print(f"  Avg constructs/increment: {v['avg_constructs_per_increment']}")
    console.print(f"  Avg hours/increment:     {v['avg_hours_per_increment']}h")

    console.print("\n[bold]Burndown[/bold]")
    console.print(f"  Completed increments:     {b['total_increments_completed']}")
    console.print(f"  Remaining TODO+PARTIAL:   {b['remaining_todo']}")
    console.print(f"  Est. increments left:     {b['estimated_increments_left']}")
    console.print(f"  Est. cost remaining:      ${b['estimated_cost_remaining']}")

    if data["increments_timeline"]:
        console.print("\n[bold]Timeline[/bold]")
        table = Table()
        table.add_column("#", justify="right")
        table.add_column("ID", style="cyan")
        table.add_column("Target LOC", justify="right")
        table.add_column("Tokens", justify="right")
        table.add_column("Cost", justify="right")
        table.add_column("Cum Cost", justify="right")
        table.add_column("Cum LOC", justify="right")

        for t in data["increments_timeline"]:
            table.add_row(
                str(t["seq"]), t["increment_id"][:15],
                str(t["target_loc"]), f"{t['tokens']:,}",
                f"${t['cost']}", f"${t['cum_cost']}",
                str(t["cum_target_loc"]),
            )
        console.print(table)

    return 0


if __name__ == "__main__":
    sys.exit(main())
