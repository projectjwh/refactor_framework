"""Structured intake interview — gathers preferences, goals, and constraints.

Runs interactively in the terminal using Rich prompts. Saves answers to
intake.yaml which informs downstream plan creation, spec generation,
and report context.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.rule import Rule

logger = logging.getLogger("refactor_framework.intake")

console = Console()


def run_intake(output_path: Path) -> dict:
    """Run the full intake interview interactively. Returns and saves answers."""
    console.print(Panel(
        "[bold]Refactoring Intake Interview[/bold]\n\n"
        "This structured interview captures your goals, constraints, and preferences\n"
        "before any refactoring begins. Answers are saved and used to inform\n"
        "architecture specs, plans, and reports.\n\n"
        "[dim]Press Enter to accept defaults shown in brackets.[/dim]",
        border_style="blue",
    ))

    answers = {
        "intake_version": "1.0",
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }

    # Phase 1: Migration Goals & Constraints
    answers["goals"] = _phase_goals()

    # Phase 2: Codebase Assessment
    answers["codebase"] = _phase_codebase()

    # Phase 3: Technical Preferences
    answers["technical"] = _phase_technical()

    # Phase 4: Risk Tolerance & QA
    answers["risk_qa"] = _phase_risk_qa()

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.dump(answers, default_flow_style=False, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    console.print()
    console.print(Panel(
        f"[bold green]Intake complete![/bold green]\n"
        f"Saved to: {output_path}\n\n"
        f"Next steps:\n"
        f"  1. Review intake.yaml and adjust if needed\n"
        f"  2. Run: [cyan]plan --files ... --description ...[/cyan]\n"
        f"  3. The intake answers will inform spec generation and reports",
        border_style="green",
    ))

    return answers


def load_intake(intake_path: Path) -> dict | None:
    """Load a completed intake from YAML."""
    if not intake_path.exists():
        return None
    return yaml.safe_load(intake_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Phase 1: Migration Goals & Constraints
# ---------------------------------------------------------------------------

def _phase_goals() -> dict:
    console.print()
    console.print(Rule("[bold blue]Phase 1: Migration Goals & Constraints"))
    console.print()

    motivation = Prompt.ask(
        "Why are you migrating this codebase?",
        choices=["modernization", "cost_reduction", "talent_availability",
                 "compliance", "performance", "end_of_life", "other"],
        default="modernization",
    )

    motivation_detail = ""
    if motivation == "other":
        motivation_detail = Prompt.ask("Please describe")

    timeline = Prompt.ask(
        "Target timeline",
        choices=["1-2 weeks", "1 month", "2-3 months", "3-6 months", "6+ months"],
        default="1 month",
    )

    budget = Prompt.ask(
        "LLM token budget ceiling (USD, 0 = no limit)",
        default="100",
    )

    team = Prompt.ask(
        "Team size working on this migration",
        choices=["solo", "2-3", "4-10", "10+"],
        default="solo",
    )

    target_env = Prompt.ask(
        "Target deployment environment",
        choices=["local", "cloud_aws", "cloud_gcp", "cloud_azure", "on_prem", "hybrid"],
        default="local",
    )

    success_def = Prompt.ask(
        "How do you define success for this migration?\n"
        "  [dim](e.g., 'all outputs match', 'passes CI', '50% LOC reduction')[/dim]",
        default="All outputs match original, all tests pass",
    )

    return {
        "motivation": motivation,
        "motivation_detail": motivation_detail,
        "timeline": timeline,
        "budget_usd": float(budget),
        "team_size": team,
        "target_environment": target_env,
        "success_definition": success_def,
    }


# ---------------------------------------------------------------------------
# Phase 2: Codebase Assessment
# ---------------------------------------------------------------------------

def _phase_codebase() -> dict:
    console.print()
    console.print(Rule("[bold blue]Phase 2: Codebase Assessment"))
    console.print()

    source_lang = Prompt.ask(
        "Source language",
        choices=["SAS", "Python", "Java", "C++", "C#", "COBOL",
                 "R", "SQL", "JavaScript", "other"],
        default="SAS",
    )

    est_loc = Prompt.ask("Estimated lines of code", default="5000")

    expertise = Prompt.ask(
        "Your expertise level in the SOURCE language",
        choices=["expert", "proficient", "familiar", "minimal"],
        default="proficient",
    )

    target_expertise = Prompt.ask(
        "Your expertise level in the TARGET language",
        choices=["expert", "proficient", "familiar", "minimal"],
        default="proficient",
    )

    pain_points = Prompt.ask(
        "Known pain points in the codebase\n"
        "  [dim](comma-separated, e.g., 'nested macros, no tests, hard-coded paths')[/dim]",
        default="",
    )

    critical_modules = Prompt.ask(
        "Critical modules that must be migrated first\n"
        "  [dim](comma-separated filenames or module names, or 'all')[/dim]",
        default="all",
    )

    test_coverage = Prompt.ask(
        "Current test coverage",
        choices=["none", "minimal", "partial", "good", "comprehensive"],
        default="none",
    )

    data_sensitivity = Prompt.ask(
        "Data sensitivity level",
        choices=["public", "internal", "confidential", "regulated_phi",
                 "regulated_pii", "regulated_financial"],
        default="internal",
    )

    return {
        "source_language": source_lang,
        "estimated_loc": int(est_loc),
        "source_expertise": expertise,
        "target_expertise": target_expertise,
        "pain_points": [p.strip() for p in pain_points.split(",") if p.strip()],
        "critical_modules": [m.strip() for m in critical_modules.split(",") if m.strip()],
        "test_coverage": test_coverage,
        "data_sensitivity": data_sensitivity,
    }


# ---------------------------------------------------------------------------
# Phase 3: Technical Preferences
# ---------------------------------------------------------------------------

def _phase_technical() -> dict:
    console.print()
    console.print(Rule("[bold blue]Phase 3: Technical Preferences"))
    console.print()

    target_lang = Prompt.ask(
        "Target language",
        choices=["Python", "Java", "C++", "Go", "Rust", "TypeScript", "other"],
        default="Python",
    )

    key_libraries = Prompt.ask(
        "Key libraries/frameworks for the target\n"
        "  [dim](comma-separated, e.g., 'polars, fastapi, pytest')[/dim]",
        default="polars",
    )

    conventions = Prompt.ask(
        "Coding conventions to follow",
        choices=["pep8_ruff", "google_style", "project_existing", "none"],
        default="pep8_ruff",
    )

    output_format = Prompt.ask(
        "Preferred data output format",
        choices=["parquet", "csv", "json", "database", "same_as_source"],
        default="parquet",
    )

    parallelism = Prompt.ask(
        "Parallelism strategy",
        choices=["multiprocessing", "threading", "asyncio",
                 "dask", "spark", "none"],
        default="multiprocessing",
    )

    idiomatic = Confirm.ask(
        "Prefer idiomatic target-language patterns over direct translation?",
        default=True,
    )

    preserve_comments = Confirm.ask(
        "Preserve source code comments as annotations in target?",
        default=False,
    )

    return {
        "target_language": target_lang,
        "key_libraries": [lib.strip() for lib in key_libraries.split(",") if lib.strip()],
        "conventions": conventions,
        "output_format": output_format,
        "parallelism": parallelism,
        "prefer_idiomatic": idiomatic,
        "preserve_comments": preserve_comments,
    }


# ---------------------------------------------------------------------------
# Phase 4: Risk Tolerance & QA
# ---------------------------------------------------------------------------

def _phase_risk_qa() -> dict:
    console.print()
    console.print(Rule("[bold blue]Phase 4: Risk Tolerance & QA"))
    console.print()

    equivalence_rigor = Prompt.ask(
        "Equivalence testing rigor",
        choices=["strict_row_match", "statistical_sample",
                 "output_shape_only", "manual_spot_check"],
        default="strict_row_match",
    )

    review_freq = Prompt.ask(
        "How often should a human review the spec before execution?",
        choices=["every_increment", "every_3rd", "critical_only", "never"],
        default="every_increment",
    )

    rollback = Prompt.ask(
        "Rollback strategy if migration fails",
        choices=["keep_source_parallel", "git_revert", "feature_flag",
                 "no_rollback_needed"],
        default="keep_source_parallel",
    )

    max_risk = Prompt.ask(
        "Maximum acceptable risk severity before blocking",
        choices=["low", "medium", "high"],
        default="medium",
    )

    approval_chain = Prompt.ask(
        "Who must approve specs before execution?\n"
        "  [dim](comma-separated names/roles, e.g., 'tech_lead, architect')[/dim]",
        default="self",
    )

    ci_integration = Confirm.ask(
        "Will you integrate with CI/CD for automated testing?",
        default=False,
    )

    return {
        "equivalence_rigor": equivalence_rigor,
        "review_frequency": review_freq,
        "rollback_strategy": rollback,
        "max_risk_severity": max_risk,
        "approval_chain": [a.strip() for a in approval_chain.split(",") if a.strip()],
        "ci_integration": ci_integration,
    }
