"""Core data models for refactoring increments."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class MappingType(Enum):
    ONE_TO_ONE = "1:1"
    ONE_TO_MANY = "1:N"
    MANY_TO_ONE = "N:1"
    REFACTORED = "refactored"
    REMOVED = "removed"
    NEW = "new"


class MappingStatus(Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    TODO = "TODO"
    REMOVED = "REMOVED"


class IncrementStatus(Enum):
    PLANNED = "planned"
    SPEC_GENERATED = "spec_generated"
    SPEC_APPROVED = "spec_approved"
    SNAPSHOT_BEFORE = "snapshot_before"
    EXECUTING = "executing"
    SNAPSHOT_AFTER = "snapshot_after"
    TESTED = "tested"
    REPORTED = "reported"
    METHODOLOGY = "methodology"
    ARCHIVED = "archived"


@dataclass
class FileMetrics:
    file_path: str = ""
    language: str = ""
    loc_total: int = 0
    loc_code: int = 0
    loc_comment: int = 0
    loc_blank: int = 0
    cyclomatic_complexity_avg: float = 0.0
    cyclomatic_complexity_max: int = 0
    halstead_volume: float = 0.0
    halstead_difficulty: float = 0.0
    halstead_effort: float = 0.0
    maintainability_index: float = 0.0
    function_count: int = 0
    class_count: int = 0


@dataclass
class IncrementSnapshot:
    phase: str = ""  # "before" or "after"
    timestamp: str = ""  # ISO format
    files: list[FileMetrics] = field(default_factory=list)
    total_loc: int = 0
    avg_complexity: float = 0.0
    avg_maintainability: float = 0.0


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    model: str = ""
    cost_estimate_usd: float = 0.0


@dataclass
class TimeRecord:
    start_time: str = ""  # ISO format
    end_time: str = ""  # ISO format
    duration_seconds: float = 0.0


@dataclass
class TestResult:
    command: str = ""
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    duration_seconds: float = 0.0
    output: str = ""


@dataclass
class EfficiencyMetrics:
    lines_changed_per_token: float = 0.0
    complexity_delta_per_hour: float = 0.0
    loc_delta: int = 0
    complexity_delta: float = 0.0
    maintainability_delta: float = 0.0


@dataclass
class ConstructMapping:
    source_file: str = ""
    source_construct: str = ""
    source_language: str = ""
    target_file: str = ""
    target_construct: str = ""
    target_language: str = ""
    mapping_type: str = "1:1"
    status: str = "TODO"
    description: str = ""
    source_line_start: int | None = None
    source_line_end: int | None = None
    target_line_start: int | None = None
    target_line_end: int | None = None


@dataclass
class MigrationConfig:
    mode: str = "same-language"  # "same-language" | "cross-language"
    source_repo: str = ""
    source_language: str = ""
    target_language: str = ""


@dataclass
class IncrementPlan:
    increment_id: str = ""
    description: str = ""
    target_files: list[str] = field(default_factory=list)
    target_patterns: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    created_at: str = ""  # ISO format
    # Cross-language migration fields
    source_files: list[str] = field(default_factory=list)
    construct_mappings: list[ConstructMapping] = field(default_factory=list)
    migration: MigrationConfig = field(default_factory=MigrationConfig)


# ---------------------------------------------------------------------------
# Architecture Spec models
# ---------------------------------------------------------------------------


@dataclass
class DesignAlternative:
    option_name: str = ""
    description: str = ""
    pros: list[str] = field(default_factory=list)
    cons: list[str] = field(default_factory=list)
    chosen: bool = False
    rationale: str = ""


@dataclass
class ModuleDecision:
    source_construct: str = ""
    source_file: str = ""
    source_description: str = ""
    target_approach: str = ""
    alternatives: list[DesignAlternative] = field(default_factory=list)
    chosen_alternative: str = ""
    rationale: str = ""


@dataclass
class ScalingConsideration:
    topic: str = ""
    current_approach: str = ""
    planned_approach: str = ""
    constraints: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class DataModelChange:
    entity_name: str = ""
    source_schema: dict = field(default_factory=dict)
    target_schema: dict = field(default_factory=dict)
    changes: list[str] = field(default_factory=list)
    grain_change: str = ""


@dataclass
class RiskItem:
    description: str = ""
    severity: str = "medium"
    likelihood: str = "medium"
    mitigation: str = ""
    owner: str = ""


@dataclass
class SpecApproval:
    approved_by: str = ""
    approved_at: str = ""
    notes: str = ""
    version: int = 1


@dataclass
class ArchitectureSpec:
    increment_id: str = ""
    generated_at: str = ""
    architecture_overview: str = ""
    module_decisions: list[ModuleDecision] = field(default_factory=list)
    scaling_considerations: list[ScalingConsideration] = field(default_factory=list)
    data_model_changes: list[DataModelChange] = field(default_factory=list)
    risks: list[RiskItem] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    approval: SpecApproval | None = None


@dataclass
class MethodologyRecord:
    increment_id: str = ""
    generated_at: str = ""
    spec_vs_actual: list[dict] = field(default_factory=list)
    data_model_comparison: list[dict] = field(default_factory=list)
    decision_log: list[dict] = field(default_factory=list)
    metrics_summary: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Top-level record
# ---------------------------------------------------------------------------


@dataclass
class IncrementRecord:
    increment_id: str = ""
    status: str = "planned"
    plan: IncrementPlan = field(default_factory=IncrementPlan)
    before: IncrementSnapshot | None = None
    after: IncrementSnapshot | None = None
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    time_record: TimeRecord = field(default_factory=TimeRecord)
    test_before: TestResult | None = None
    test_after: TestResult | None = None
    efficiency: EfficiencyMetrics = field(default_factory=EfficiencyMetrics)
    diff_summary: dict = field(default_factory=dict)
    spec: ArchitectureSpec | None = None
    methodology: MethodologyRecord | None = None
