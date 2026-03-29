# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Refactor Framework — a CLI-driven Python tool for systematic legacy codebase refactoring with planning, execution tracking, metrics computation, and HTML report generation. Each refactoring increment follows a plan→snapshot→execute→test→report→archive lifecycle.

## Commands

```bash
# Install (editable, with dev dependencies)
pip install -e ".[dev]"

# Run CLI
python -m refactor_framework <command> [options]
# Commands: init, plan, snapshot, execute, test, report, status, history

# Lint
ruff check src/ tests/

# Run all tests
pytest

# Run single test file
pytest tests/test_snapshot/test_metrics.py

# Run with coverage
pytest --cov=refactor_framework
```

## Architecture

Six-phase workflow per increment, each backed by a subpackage under `src/refactor_framework/`:

1. **plan/** — Create increment plans: define scope (file globs), description, acceptance criteria. Generates increment ID (ISO timestamp) and `plan.yaml`.
2. **snapshot/** — Capture before/after file states. Copies files, computes metrics via radon (LOC, cyclomatic complexity, Halstead, maintainability index) and optionally lizard.
3. **execute/** — Track refactoring execution: start/stop timestamps, token usage (input/output), model name, cost estimation.
4. **test/** — Run test suite via subprocess, parse pytest output for pass/fail/error/skip counts.
5. **report/** — Generate HTML reports: per-increment (side-by-side diffs, metrics comparison table, token/time summary) and aggregate dashboard (cumulative charts, efficiency metrics, history table).
6. **archive/** — Persist increment records to JSON (default) or SQLite ledger for longitudinal queries.

Key supporting modules:
- `config.py` — Loads `config/default.yaml` into nested dataclasses via `_build_dataclass()` recursive constructor
- `models.py` — Core dataclasses: `IncrementRecord`, `FileMetrics`, `TokenUsage`, `TimeRecord`, `EfficiencyMetrics`, etc.
- `utils/` — Logging (Rich-based), path helpers, ISO timestamp ID generation
- `templates/` — Jinja2 HTML templates (`_base.html`, `increment_report.html`, `dashboard.html`)

## Key Design Decisions

- **Dataclasses** (not pydantic) for all models — lightweight, matches workspace convention
- **argparse** CLI with subcommands — no click/typer dependency
- **JSON ledger** as default persistence (human-readable, git-friendly), SQLite as opt-in alternative
- **radon** for Python metrics (CC, LOC, MI, Halstead), **lizard** for multi-language support
- **difflib** (stdlib) for diff generation — both side-by-side HTML and unified format
- **Jinja2** templates with inline CSS (no external assets) — reports open in any browser
- **Increment IDs** are ISO timestamps (e.g., `20260326T143022`) — sortable, human-readable
- **Subprocess isolation** for test running — framework never imports target codebase
- Windows-compatible: ASCII column headers in Rich tables (no Unicode deltas)

## Configuration

All settings in `config/default.yaml`. Override with `--config path/to/custom.yaml` on any CLI command. The `init` command updates the config with the target repo path.

## Testing

Tests mirror source structure under `tests/`. 62 tests covering all modules. Test fixtures in `tests/fixtures/` include `sample_before.py` (high complexity) and `sample_after.py` (refactored).
