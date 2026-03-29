"""Execution time and token tracking."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from refactor_framework.config import AppConfig
from refactor_framework.models import TimeRecord, TokenUsage

logger = logging.getLogger("refactor_framework.execute")


def start_execution(config: AppConfig, increment_id: str) -> str:
    """Record execution start time. Returns the ISO timestamp."""
    inc_dir = Path(config.project.increments_dir) / increment_id
    if not inc_dir.exists():
        raise FileNotFoundError(f"Increment directory not found: {inc_dir}")

    start_time = datetime.now(timezone.utc).isoformat()
    start_file = inc_dir / "execution_start.json"
    start_file.write_text(json.dumps({"start_time": start_time}), encoding="utf-8")

    logger.info("Execution started for %s at %s", increment_id, start_time)
    return start_time


def stop_execution(
    config: AppConfig,
    increment_id: str,
    tokens_input: int = 0,
    tokens_output: int = 0,
    model: str | None = None,
    cost_per_input: float | None = None,
    cost_per_output: float | None = None,
) -> tuple[TimeRecord, TokenUsage]:
    """Record execution stop time and token usage.

    Returns (TimeRecord, TokenUsage) with computed duration and cost.
    """
    inc_dir = Path(config.project.increments_dir) / increment_id
    start_file = inc_dir / "execution_start.json"

    if not start_file.exists():
        raise FileNotFoundError(
            f"No execution_start.json found for {increment_id}. Run 'execute --action start' first."
        )

    start_data = json.loads(start_file.read_text(encoding="utf-8"))
    start_time = start_data["start_time"]
    end_time = datetime.now(timezone.utc).isoformat()

    # Compute duration
    start_dt = datetime.fromisoformat(start_time)
    end_dt = datetime.fromisoformat(end_time)
    duration = (end_dt - start_dt).total_seconds()

    time_record = TimeRecord(
        start_time=start_time,
        end_time=end_time,
        duration_seconds=duration,
    )

    # Compute token cost
    used_model = model or config.execute.default_model
    cpi = cost_per_input if cost_per_input is not None else config.execute.cost_per_input_token
    cpo = cost_per_output if cost_per_output is not None else config.execute.cost_per_output_token
    total_tokens = tokens_input + tokens_output
    cost = (tokens_input * cpi) + (tokens_output * cpo)

    token_usage = TokenUsage(
        input_tokens=tokens_input,
        output_tokens=tokens_output,
        total_tokens=total_tokens,
        model=used_model,
        cost_estimate_usd=round(cost, 6),
    )

    # Persist
    end_file = inc_dir / "execution_end.json"
    end_file.write_text(
        json.dumps({
            "time_record": {
                "start_time": time_record.start_time,
                "end_time": time_record.end_time,
                "duration_seconds": time_record.duration_seconds,
            },
            "token_usage": {
                "input_tokens": token_usage.input_tokens,
                "output_tokens": token_usage.output_tokens,
                "total_tokens": token_usage.total_tokens,
                "model": token_usage.model,
                "cost_estimate_usd": token_usage.cost_estimate_usd,
            },
        }, indent=2),
        encoding="utf-8",
    )

    logger.info(
        "Execution stopped for %s: %.1fs, %d tokens, $%.4f",
        increment_id, duration, total_tokens, cost,
    )
    return time_record, token_usage


def load_execution_data(
    increments_dir: str, increment_id: str
) -> tuple[TimeRecord, TokenUsage] | None:
    """Load execution data from an increment directory, if it exists."""
    end_file = Path(increments_dir) / increment_id / "execution_end.json"
    if not end_file.exists():
        return None

    data = json.loads(end_file.read_text(encoding="utf-8"))
    tr = data.get("time_record", {})
    tu = data.get("token_usage", {})

    return (
        TimeRecord(
            start_time=tr.get("start_time", ""),
            end_time=tr.get("end_time", ""),
            duration_seconds=tr.get("duration_seconds", 0.0),
        ),
        TokenUsage(
            input_tokens=tu.get("input_tokens", 0),
            output_tokens=tu.get("output_tokens", 0),
            total_tokens=tu.get("total_tokens", 0),
            model=tu.get("model", ""),
            cost_estimate_usd=tu.get("cost_estimate_usd", 0.0),
        ),
    )
