# Commander Agent Evaluation: refactor_framework

**Product**: refactor_framework v0.1.0
**Scope**: 4,687 LOC (src), 1,193 LOC (tests), 75 tests, 18 CLI commands
**Evaluated by**: Marcus Chen (Tech Lead), Aisha Okafor (Data Architect), Derek Nakamura (Software Engineer)
**Skills applied**: code-review, architecture-decision, security-review, performance-review
**Date**: 2026-03-29

---

## 1. Marcus Chen — Tech Lead Review

### Operability: "What happens when this breaks at 2am?"

| Area | Finding | Severity |
|------|---------|----------|
| Ledger corruption | JSON ledger (`output/ledger.json`) has no locking. Two concurrent `execute --action stop` calls can corrupt the file. No backup, no WAL. | **must-fix** |
| Increment state | If a snapshot fails mid-copy (disk full, permission error), status is updated in ledger but files are partial. No rollback, no integrity check on resume. | **should-fix** |
| Error recovery | `next` command shows the right step, but there's no `reset` or `retry` command to recover a stuck increment. You'd have to manually edit ledger.json. | **should-fix** |
| Logs | Logging goes to stderr via Rich. No persistent log file per increment. At 3am you have no history of what happened — only the JSON artifacts. | **should-fix** |

**3am Test Verdict**: Partially passes. Someone could run `status` and `next` to understand the state, but recovering from a failure requires manual JSON editing.

### Boring Alternative Audit

| Dependency | Verdict | Notes |
|------------|---------|-------|
| **PyYAML** (6.0) | RETAIN | Boring, zero-dep, industry standard |
| **Jinja2** (3.1) | RETAIN | Boring, widely used, 1 transitive dep (MarkupSafe) |
| **Rich** (13.7) | WATCH | 2 transitive deps (markdown-it-py, pygments). Could be replaced by plain `print()` + `tabulate` for less surface area. But Rich is well-maintained. |
| **radon** (6.0) | RETAIN | Niche but stable. 2 transitive deps (colorama, mando). Python-specific, which is fine. |
| **lizard** (1.21) | RETAIN | Multi-language complexity. 2 transitive deps (pathspec, pygments). Shared pygments with Rich. |
| **unidiff** (0.7) | WATCH | Zero-dep, but only used for parsing unified diffs — currently imported but barely utilized. `difflib` stdlib handles most needs. Consider removing. |

**Dependency total**: 6 direct, ~7 transitive. Acceptable for the scope. No red flags.

### Build vs. Buy Assessment

| Capability | Verdict | Notes |
|------------|---------|-------|
| SAS parser (scaffold.py) | BUILD justified | No existing SAS→construct parser in Python. Regex-based, ~170 LOC. Appropriate scope. |
| Metrics (radon+lizard) | BUY correct | Standard tools, well-maintained. Not reinventing. |
| Diff generation (difflib) | BUY correct | stdlib. No library needed. |
| Token tracking | BUILD justified | Simple start/stop timer + arithmetic. No LLM SDK dependency in core (anthropic is optional). |
| Equivalence testing | BUILD justified | Polars-based comparison. No existing cross-format data differ covers SAS→Parquet comparison. |
| Report generation | BUILD justified | Custom templates with project-specific sections. Generic report tools wouldn't cover construct mapping or methodology docs. |

### Marcus Chen Verdict: **APPROVED WITH CONDITIONS**

Conditions:
1. Add file-level locking to JSON ledger (or migrate to SQLite as default)
2. Add `reset` CLI command to recover stuck increments
3. Add persistent per-increment log file

---

## 2. Aisha Okafor — Data Architect Review

### Data Model Assessment

**models.py: 20+ dataclasses, 3 enums**

| Model | Grain | Consumption | Finding | Severity |
|-------|-------|-------------|---------|----------|
| `IncrementRecord` | 1 per increment_id | Ledger, all reports | Well-defined. But `diff_summary: dict` is untyped — should be a dataclass or TypedDict. | **nit** |
| `FileMetrics` | 1 per file per snapshot | Reports, dashboards | Good. `language` field added properly. Missing: `file_hash` for change detection. | **should-fix** |
| `ConstructMapping` | 1 per source construct per increment | Mapping reports, coverage | Good grain. But no unique constraint — duplicate mappings for same source_construct are silently accepted. | **should-fix** |
| `ArchitectureSpec` | 1 per increment | Spec.md, methodology | Heavy nesting (Spec→ModuleDecision→DesignAlternative). Serialization roundtrip untested for this depth. | **must-fix** |
| `MethodologyRecord` | 1 per increment | methodology.html | Uses `list[dict]` for `spec_vs_actual`, `decision_log`. Should be typed dataclasses for schema stability. | **should-fix** |
| `MigrationConfig` | 1 per plan | Planner, snapshot | Good. Cleanly separated from IncrementPlan. |  |

### Schema Evolution Concern

**Critical finding**: `_dict_to_record()` in `ledger.py:138` reconstructs `IncrementPlan` by popping `construct_mappings` and `migration` before `**kwargs` construction. But `ArchitectureSpec` and `MethodologyRecord` deserialization is NOT implemented in the ledger — the `spec` and `methodology` fields on `IncrementRecord` are new but `_dict_to_record()` never rebuilds them from JSON. They'll always be `None` when loaded from ledger.

**Severity**: **must-fix** — spec and methodology data is silently lost on ledger round-trip.

### Entity-Relationship Analysis

```
IncrementRecord (root)
  ├── IncrementPlan (1:1)
  │     ├── ConstructMapping (1:N)
  │     └── MigrationConfig (1:1)
  ├── IncrementSnapshot before (0..1)
  │     └── FileMetrics (1:N)
  ├── IncrementSnapshot after (0..1)
  │     └── FileMetrics (1:N)
  ├── TokenUsage (1:1)
  ├── TimeRecord (1:1)
  ├── TestResult before (0..1)
  ├── TestResult after (0..1)
  ├── EfficiencyMetrics (1:1)
  ├── ArchitectureSpec (0..1)        ← NOT deserialized from ledger
  │     ├── ModuleDecision (1:N)
  │     │     └── DesignAlternative (1:N)
  │     ├── ScalingConsideration (1:N)
  │     ├── DataModelChange (1:N)
  │     ├── RiskItem (1:N)
  │     └── SpecApproval (0..1)
  └── MethodologyRecord (0..1)       ← NOT deserialized from ledger
```

**Nesting depth**: 4 levels (Record → Spec → ModuleDecision → DesignAlternative). The generic `_build_dataclass` pattern from config.py would help here but isn't used for ledger deserialization.

### Consumption Pattern

| Consumer | Reads | Pattern |
|----------|-------|---------|
| `status` | All records, summary fields only | Scan |
| `history` | All records, aggregated | Full scan + compute |
| `coverage` | All records, construct_mappings only | Scan + group-by |
| `burndown` | All records, all fields | Full scan + time-series |
| `report` | Single record + plan files | Point lookup |
| `methodology` | Single record + spec.json | Point lookup + file read |

**Finding**: Every read command loads ALL records via `ledger.list_all()` — even `report` which only needs one. At 100+ increments this will be slow with JSON backend.

**Severity**: **should-fix** — add `ledger.get()` usage for single-record commands (already exists but `coverage` and `burndown` don't use it).

### Aisha Okafor Verdict: **APPROVED WITH CONDITIONS**

Conditions:
1. Fix `_dict_to_record()` to deserialize `spec` and `methodology` fields
2. Add deduplication check on `ConstructMapping` (same source_construct in same increment)
3. Type the `dict` fields in `MethodologyRecord` as proper dataclasses

---

## 3. Derek Nakamura — Software Engineer (DX) Review

### CLI Invocation Analysis (18 commands)

| Command | Invocation | DX Grade | Notes |
|---------|-----------|----------|-------|
| `init` | `init --target-repo PATH` | A | Clean, one required arg |
| `intake` | `intake` | A | Zero args, fully interactive |
| `plan` | `plan --files "*.py" --description "..." --source-repo ... --source-files ...` | B | Many flags for cross-language. Could use `--from` / `--to` shorthand. |
| `map` | `map --increment-id ID --mappings-file PATH` | A | Clear |
| `scaffold` | `scaffold --source-dir PATH --patterns "*.sas" --output PATH` | B | `--patterns` default is `["*.sas"]` — too opinionated. Should default to `["*"]` or require it. |
| `spec` | `spec --increment-id ID` | A | Clean |
| `approve` | `approve --increment-id ID --approved-by NAME` | A | Clear |
| `snapshot` | `snapshot --increment-id ID --phase before` | A | Clear |
| `execute` | `execute --increment-id ID --action stop --tokens-total 30000` | B- | `--action start` and `--action stop` have different valid flags. Confusing that `--tokens-total` is silently ignored on `start`. Should be subcommands: `execute start ID`, `execute stop ID --tokens-total N`. |
| `validate` | `validate --source-output ... --target-output ... --key "BENE_ID,YEAR"` | B | `--key` as comma-separated string instead of `nargs="+"` is inconsistent with `--files` which uses nargs. |
| `report` | `report --increment-id ID` or `report --all` | A | Clean, mutually exclusive |
| `methodology` | `methodology --increment-id ID` | A | Clean |
| `next` | `next` | A+ | Zero args, guides the user. Best command in the CLI. |
| `coverage` | `coverage [--format json]` | A | Clean |
| `burndown` | `burndown [--format json]` | A | Clean |
| `status` | `status` | A | Clean |
| `history` | `history [--format json]` | A | Clean |
| `test` | `test --increment-id ID --phase before --command "pytest"` | A | Clear |

### Output Composability

| Command | Human output | JSON output | Pipeable? |
|---------|-------------|-------------|-----------|
| `status` | Rich table | No | **No** — Rich table can't be piped to grep/jq |
| `history` | Rich table | `--format json` | Yes (json mode) |
| `coverage` | Rich table | `--format json` | Yes (json mode) |
| `burndown` | Rich table | `--format json` | Yes (json mode) |
| `next` | Plain text | No | Partially — text is parseable but not structured |
| `plan` | Plain text | No | **No** — should output JSON with increment_id for scripting |

**Finding**: `status` has no `--format json` option. This is the command most likely to be scripted.

**Severity**: **should-fix**

### Error Message Quality

| Error | Message | Actionable? | Grade |
|-------|---------|-------------|-------|
| Missing file | `"Error: target repo not found: /path"` | Yes | B+ |
| Spec not approved | `"Error: spec exists but is not approved. Review... then run: approve..."` | Yes, with exact command | A |
| No increment | `"No intake completed. Run: intake"` | Yes | A |
| Missing spec | `"Error: no spec found for ID"` | Partial — doesn't say what to do | **B-** |
| No increment in ledger | `"Error: increment ID not found in ledger"` | No — doesn't suggest checking `status` | **C** |

**Finding**: Some errors tell you what went wrong but not what to do. The approval gate error is the gold standard — all errors should match that pattern.

**Severity**: **should-fix**

### 3am Incident Test

**Scenario**: Increment stuck in "executing" status, user left the session.

1. Run `next` → tells you to stop execution. **Good.**
2. Run `execute --action stop --tokens-total 0` → works, records 0 tokens. **Good.**
3. Run `status` → shows the increment with status. **Good.**
4. What if you want to restart from scratch? **No `reset` command.** Must manually delete increment directory and edit ledger.json. **Fail.**

### Setup Friction

```
git clone → pip install -e ".[dev]" → python -m refactor_framework init --target-repo PATH → intake → plan
```

**3 commands to first meaningful output** (init + intake + plan). This is good. But `intake` is interactive and blocks scripting. There should be a `--skip-intake` or `--quick` flag on plan for users who don't want the interview.

**Severity**: **nit**

### Derek Nakamura Verdict: **APPROVED WITH CONDITIONS**

Conditions:
1. Add `--format json` to `status` command
2. Add `--format json` to `plan` output (return increment_id for scripting)
3. Fix error messages to always include the remediation command
4. Consider splitting `execute start/stop` into separate subcommands

---

## 4. Code Review — 4-Lens Protocol

### Correctness Lens

| # | Finding | File | Severity |
|---|---------|------|----------|
| C1 | `_apply_basic_metrics` comment detection: `line.strip()[0:2] in comment_markers` fails for single-char markers like `#`. The slice `[0:2]` is 2 chars but `#` is 1 char. Also `line.strip().startswith(comment_markers)` is redundant after the `in` check. | `snapshot/metrics.py:149` | **should-fix** |
| C2 | `scaffold.py` regex `_MACRO_END` matches `%MEND` with optional name, but if a macro doesn't have `%MEND`, the macro_stack never pops — constructs after it get attributed to the wrong parent. | `mapping/scaffold.py:41` | **should-fix** |
| C3 | `equivalence.py` `_read_file` for `.sas7bdat` requires pyreadstat + pandas → polars conversion. But pyreadstat is not in dependencies and will fail with an unhelpful ImportError at runtime. | `validate/equivalence.py:135` | **should-fix** |
| C4 | `spec/generator.py` `generate_spec` always generates 2 default alternatives (A: Direct translation, B: Idiomatic rewrite) even when construct_mappings is empty. This produces a spec with module decisions but no source constructs. | `spec/generator.py:30-68` | **nit** |
| C5 | No test coverage for `spec/`, `methodology/`, `intake/`, `validate/`, `mapping/scaffold.py`, `mapping/coverage.py`, `mapping/migration_plan.py`. Only `mapping/loader.py` has tests. **56% of new modules are untested.** | `tests/` | **must-fix** |

### Security Lens

| # | Finding | File | Severity |
|---|---------|------|----------|
| S1 | `test/runner.py:48` uses `shell=True` with user-provided command string. If the test command comes from config or CLI `--command` flag, this is a shell injection vector. | `test/runner.py:46-52` | **must-fix** |
| S2 | `yaml.safe_load()` used consistently (not `yaml.load()`). Good. | All YAML loading | pass |
| S3 | Token cost data (`cost_estimate_usd`) stored in plaintext JSON. Not sensitive per se, but if this framework processes PHI/PII codebases, the file paths and code snippets in `spec.json` and snapshot directories could contain sensitive data. No encryption at rest. | `archive/ledger.py`, `spec.json` | **nit** (depends on data sensitivity) |
| S4 | No input validation on `--increment-id` — accepts any string. Could be used for path traversal: `--increment-id "../../etc"` would create directories outside the intended location. | `__main__.py` (all commands) | **should-fix** |

### Performance Lens

| # | Finding | File | Severity |
|---|---------|------|----------|
| P1 | `coverage` and `burndown` commands call `ledger.list_all()` which loads every record into memory. At 500+ increments with full spec/methodology data, this could be 100MB+. | `__main__.py:768,823` | **should-fix** |
| P2 | `scaffold.py` uses `repo.rglob("*")` + `fnmatch` for file matching. On a large codebase (100K+ files), this iterates every file. Should use specific `rglob(pattern)` instead. | `plan/planner.py:28` | **nit** |
| P3 | `compute_file_metrics` reads the entire file into memory as a string. For very large SAS files (50K+ lines), this is fine. No streaming needed at this scale. | `snapshot/metrics.py:39` | pass |

### DX Lens

| # | Finding | File | Severity |
|---|---------|------|----------|
| D1 | `__main__.py` is 840+ lines — the largest file in the project. All 18 command handlers are in one file. Should be split into `cli/commands/` modules. | `__main__.py` | **should-fix** |
| D2 | `models.py` has 20+ dataclasses in one file (230+ lines). Manageable but approaching the point where it should split into `models/core.py`, `models/spec.py`, `models/methodology.py`. | `models.py` | **nit** |
| D3 | Inconsistent `--format` availability: `history`, `coverage`, `burndown` have it; `status`, `plan`, `next` don't. | `__main__.py` | **should-fix** |

---

## 5. Architecture Decision — Antagonistic Challenge

### Challenge 1: "Why build this instead of using git diff + a spreadsheet?"

**Counter-argument**: Git diff + a spreadsheet gives you 80% of the value for 0% of the code. `git diff --stat` shows LOC changes. A spreadsheet tracks tokens and cost. Construct mappings can live in a Google Doc.

**Defense**: The framework's value is the **integration** — linking construct mappings to code snapshots to metrics to reports to burndown in one auditable workflow. A spreadsheet can't auto-scaffold 29 constructs from SAS source, generate side-by-side annotated HTML panels, or enforce an approval gate before execution. The framework encodes institutional knowledge about the migration process that a spreadsheet loses.

**Verdict**: Build is justified for teams doing repeated migrations. For a one-off migration, the spreadsheet approach is sufficient.

### Challenge 2: "JSON ledger instead of SQLite — why?"

**Counter-argument**: JSON ledger has no locking, no concurrent access, no querying capability. SQLite is stdlib, zero-dep, and solves all three problems.

**Defense**: JSON was chosen for human readability and git-friendliness. The SQLite backend already exists as an option.

**Verdict**: SQLite should be the **default**, not JSON. The JSON backend should remain as a `--ledger-backend json` opt-in for debugging. This is the single highest-impact architectural change.

### Challenge 3: "18 CLI commands — is this too many?"

**Counter-argument**: Unix philosophy says each tool does one thing. But 18 commands is a lot to learn. `kubectl` has ~40 but also has `kubectl help` with grouping.

**Defense**: The `next` command solves discoverability — you never need to memorize the workflow. Commands are grouped by lifecycle phase (plan, execute, report, analyze).

**Verdict**: Acceptable. But the `--help` output should group commands by phase, not list them alphabetically.

---

## 6. Security Review — Mandatory Controls

### Data Classification

| Data Element | Classification | Notes |
|---|---|---|
| Source code snippets (spec.json, snapshots) | **Confidential** | Could contain business logic, algorithms |
| Token costs | Internal | Financial but low sensitivity |
| Intake answers | Internal | Team structure, pain points |
| Construct mappings | Internal | Architecture knowledge |
| File paths | Internal | Reveals directory structure |

### Credential Audit

- No hardcoded secrets found in source code. **Pass.**
- No API keys stored. Token tracking is manual input, not API integration. **Pass.**
- `intake.yaml` may contain team names and approval chain — not credentials but could be PII-adjacent. **Pass with note.**

### Mandatory Controls Checklist

| Control | Status | Notes |
|---------|--------|-------|
| Input validation on CLI args | **FAIL** | `--increment-id` not validated (path traversal risk) |
| Shell injection prevention | **FAIL** | `shell=True` in `test/runner.py` |
| YAML safe loading | **PASS** | `yaml.safe_load()` used everywhere |
| Dependency pinning | **PARTIAL** | Version ranges in pyproject.toml, not pinned |
| No secrets in logs | **PASS** | Logging is minimal, no sensitive data logged |

### Security Verdict: **APPROVED WITH CONDITIONS**

Conditions:
1. Validate `--increment-id` against `_ID_PATTERN` regex before use
2. Replace `shell=True` with `shlex.split()` + `shell=False` in test runner

---

## Consolidated Action Items

### Must-Fix (3 items)

| # | Finding | Owner | Effort |
|---|---------|-------|--------|
| 1 | **Ledger: `spec` and `methodology` not deserialized from JSON** — data silently lost on round-trip | Aisha | Small |
| 2 | **Shell injection via `shell=True`** in test/runner.py | Security | Small |
| 3 | **56% of new modules untested** — spec/, methodology/, intake/, validate/, scaffold, coverage, migration_plan | Derek | Medium |

### Should-Fix (10 items)

| # | Finding | Owner | Effort |
|---|---------|-------|--------|
| 4 | Validate `--increment-id` against ID regex to prevent path traversal | Security | Small |
| 5 | Add `--format json` to `status` command | Derek | Small |
| 6 | Add `reset` command to recover stuck increments | Marcus | Small |
| 7 | Add persistent per-increment log file | Marcus | Small |
| 8 | Fix `_apply_basic_metrics` comment detection logic | Derek | Small |
| 9 | Add dedup check on ConstructMapping (same source_construct) | Aisha | Small |
| 10 | Type `MethodologyRecord` dict fields as proper dataclasses | Aisha | Small |
| 11 | Make all error messages include remediation command | Derek | Medium |
| 12 | Add file locking to JSON ledger (or default to SQLite) | Marcus | Medium |
| 13 | Split `__main__.py` (840 LOC) into command modules | Derek | Medium |

### Nit (4 items)

| # | Finding | Owner |
|---|---------|-------|
| 14 | `IncrementRecord.diff_summary` should be typed | Aisha |
| 15 | `scaffold --patterns` default too opinionated (*.sas) | Derek |
| 16 | Group commands by phase in `--help` output | Derek |
| 17 | `spec` generates default alternatives even with empty mappings | Derek |

---

## Overall Verdicts

| Agent | Verdict | Key Concern |
|-------|---------|-------------|
| **Marcus Chen** (Tech Lead) | Approved with conditions | Ledger durability, no reset command |
| **Aisha Okafor** (Data Architect) | Approved with conditions | Spec/methodology not persisted through ledger, untyped dicts |
| **Derek Nakamura** (Software Engineer) | Approved with conditions | Test coverage gaps, inconsistent --format, error messages |
| **Security Review** | Approved with conditions | shell=True, increment-id validation |
| **Performance Review** | Pass | Acceptable for current scale (<500 increments) |

**Composite Verdict**: **APPROVED WITH CONDITIONS** — 3 must-fix items before production use, 10 should-fix items for next release.
