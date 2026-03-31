"""AI engine for auto mode — wraps Anthropic API for spec filling,
construct mapping, and code generation.

Requires: pip install refactor-framework[llm]
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from refactor_framework.models import ArchitectureSpec, ConstructMapping, IncrementPlan

logger = logging.getLogger("refactor_framework.pipeline")


class AIEngine:
    """LLM integration for automated pipeline mode."""

    def __init__(self, api_key: str, model: str, budget_tokens: int = 100000):
        try:
            from anthropic import Anthropic
        except ImportError:
            raise ImportError(
                "anthropic SDK required for auto mode. "
                "Install with: pip install refactor-framework[llm]"
            )
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.budget = budget_tokens
        self.tokens_used_input = 0
        self.tokens_used_output = 0

    @property
    def tokens_remaining(self) -> int:
        return self.budget - self.tokens_used_input - self.tokens_used_output

    def _call(self, system: str, prompt: str, max_tokens: int = 1000) -> str:
        """Make a single API call, track tokens, respect budget."""
        if self.tokens_remaining < max_tokens:
            logger.warning("Token budget nearly exhausted, skipping API call")
            return ""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )

        self.tokens_used_input += response.usage.input_tokens
        self.tokens_used_output += response.usage.output_tokens
        logger.info(
            "API call: %d in + %d out tokens",
            response.usage.input_tokens, response.usage.output_tokens,
        )

        return response.content[0].text if response.content else ""

    def map_construct_targets(
        self,
        scaffold_mappings: list[dict],
        source_repo: str,
    ) -> list[ConstructMapping]:
        """Use LLM to suggest target file/construct for scaffolded mappings."""
        system = (
            "You are a code migration expert. Given SAS source constructs, "
            "suggest Python target file names and function/class names. "
            "Respond with JSON only."
        )

        constructs_summary = "\n".join(
            f"- {m.get('source_construct', '')} in {m.get('source_file', '')} "
            f"({m.get('description', '')})"
            for m in scaffold_mappings[:30]  # limit to avoid token overflow
        )

        prompt = (
            f"These SAS constructs need Python equivalents:\n\n"
            f"{constructs_summary}\n\n"
            f"For each, suggest a target Python file and function/class name. "
            f"Respond with a JSON array:\n"
            f'[{{"source_construct": "...", "target_file": "...", '
            f'"target_construct": "...", "description": "..."}}]'
        )

        response = self._call(system, prompt, max_tokens=2000)
        if not response:
            return [ConstructMapping(**m) for m in scaffold_mappings]

        try:
            suggestions = json.loads(response)
            # Merge suggestions into scaffold mappings
            suggestion_map = {s["source_construct"]: s for s in suggestions}
            result = []
            for m in scaffold_mappings:
                valid_keys = ConstructMapping.__dataclass_fields__
                cm = ConstructMapping(
                    **{k: v for k, v in m.items() if k in valid_keys}
                )
                s = suggestion_map.get(m.get("source_construct", ""))
                if s:
                    cm.target_file = s.get("target_file", "")
                    cm.target_construct = s.get("target_construct", "")
                    if s.get("description"):
                        cm.description = s["description"]
                result.append(cm)
            return result
        except (json.JSONDecodeError, KeyError):
            logger.warning("Failed to parse LLM mapping response, using scaffold defaults")
            return [ConstructMapping(**m) for m in scaffold_mappings]

    def fill_spec_placeholders(
        self,
        spec: ArchitectureSpec,
        plan: IncrementPlan,
        intake: dict,
    ) -> ArchitectureSpec:
        """Fill [TO BE FILLED] and [FILL IN:] placeholders in the spec."""
        system = (
            "You are a software architect writing migration specs. "
            "Be concise (1-3 sentences per response). No markdown formatting."
        )

        # Fill architecture overview
        if "[FILL IN:" in spec.architecture_overview:
            target_lang = plan.migration.target_language or "Python"
            source_lang = plan.migration.source_language or "SAS"
            libs = intake.get("technical", {}).get("key_libraries", [])
            prompt = (
                f"Describe the target {target_lang} module structure for a "
                f"migration from {source_lang}. "
                f"Files: {', '.join(plan.target_files)}. "
                f"Libraries: {', '.join(libs)}. "
                f"3-4 lines: main entry points, module responsibilities, call flow."
            )
            overview_fill = self._call(system, prompt, max_tokens=300)
            if overview_fill:
                spec.architecture_overview = spec.architecture_overview.replace(
                    "\n[FILL IN: Main entry points, module structure, call graph]",
                    "\n" + overview_fill,
                )

        # Fill module decision rationales
        for md in spec.module_decisions:
            if "[TO BE FILLED]" in md.rationale:
                chosen = md.chosen_alternative
                source = md.source_description[:200]
                prompt = (
                    f"We chose '{chosen}' for migrating: {source}. "
                    f"Explain in 1-2 sentences why this approach is preferred."
                )
                rationale = self._call(system, prompt, max_tokens=150)
                if rationale:
                    md.rationale = rationale

            for alt in md.alternatives:
                if "[TO BE FILLED" in alt.rationale:
                    alt.rationale = md.rationale

        # Fill scaling planned approaches
        for sc in spec.scaling_considerations:
            if "[FILL IN:" in sc.planned_approach:
                parallelism = intake.get("technical", {}).get("parallelism", "multiprocessing")
                sc.planned_approach = f"Use {parallelism} for parallel execution"

        # Fill data model changes
        for dm in spec.data_model_changes:
            if "[FILL IN:" in dm.entity_name:
                dm.entity_name = "Enrollment output (bene_enroll)"
            dm.changes = [c for c in dm.changes if "[FILL IN:" not in c]
            if not dm.changes:
                dm.changes = ["See construct mappings for detailed schema changes"]
            if "[FILL IN:" in dm.grain_change:
                dm.grain_change = "row-per-month input -> row-per-year output"

        # Fill acceptance criteria
        spec.acceptance_criteria = [
            c for c in spec.acceptance_criteria if not c.startswith("[")
        ]
        if not spec.acceptance_criteria:
            spec.acceptance_criteria = [
                "All output rows match source equivalence test",
                "All QA checks pass (no duplicates, valid string lengths)",
                intake.get("goals", {}).get("success_definition", "Tests pass"),
            ]

        # Fill risk mitigations
        for r in spec.risks:
            if "[TO BE FILLED]" in r.mitigation:
                r.mitigation = "Address during implementation; validate in testing phase"

        return spec

    def generate_refactored_code(
        self,
        source_file: Path,
        target_language: str,
        spec: ArchitectureSpec,
    ) -> str:
        """Generate refactored target code from a source file."""
        source_code = source_file.read_text(encoding="utf-8", errors="replace")

        # Find relevant module decisions
        relevant_decisions = [
            md for md in spec.module_decisions
            if md.source_file == source_file.name
        ]
        decisions_context = "\n".join(
            f"- {md.source_construct}: {md.rationale}"
            for md in relevant_decisions
        )

        system = (
            f"You are a code migration expert. Convert the given source code "
            f"to {target_language}. Follow these architectural decisions:\n"
            f"{decisions_context}\n\n"
            f"Output ONLY the target {target_language} code, no explanations."
        )

        prompt = (
            f"Convert this code to {target_language}:\n\n"
            f"```\n{source_code[:8000]}\n```"
        )

        code = self._call(system, prompt, max_tokens=4000)

        # Strip markdown code fences if present
        if code.startswith("```"):
            lines = code.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            code = "\n".join(lines)

        return code
