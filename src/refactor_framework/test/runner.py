"""Test suite execution and result parsing."""

from __future__ import annotations

import json
import logging
import re
import subprocess
import time
from pathlib import Path

from refactor_framework.config import AppConfig
from refactor_framework.models import TestResult

logger = logging.getLogger("refactor_framework.test")


def run_tests(
    config: AppConfig,
    increment_id: str,
    phase: str,
    command: str | None = None,
) -> TestResult:
    """Run the test suite and record results.

    Parameters
    ----------
    config : AppConfig
    increment_id : str
    phase : str
        "before" or "after"
    command : str or None
        Test command to run. Defaults to config.test.default_command.
    """
    if phase not in ("before", "after"):
        raise ValueError(f"Phase must be 'before' or 'after', got '{phase}'")

    cmd = command or config.test.default_command
    cwd = config.test.working_directory or config.project.target_repo
    timeout = config.test.timeout_seconds

    logger.info("Running tests for %s (%s): %s", increment_id, phase, cmd)

    start = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = proc.stdout + proc.stderr
        duration = time.monotonic() - start
    except subprocess.TimeoutExpired:
        duration = time.monotonic() - start
        output = f"Test command timed out after {timeout}s"
        logger.error(output)
        return TestResult(command=cmd, errors=1, duration_seconds=duration, output=output)

    # Parse pytest summary line
    passed, failed, errors, skipped = _parse_pytest_output(output)

    result = TestResult(
        command=cmd,
        passed=passed,
        failed=failed,
        errors=errors,
        skipped=skipped,
        duration_seconds=round(duration, 2),
        output=output[-5000:],  # Truncate to last 5000 chars
    )

    # Persist
    inc_dir = Path(config.project.increments_dir) / increment_id
    result_file = inc_dir / f"test_{phase}.json"
    result_file.write_text(
        json.dumps({
            "command": result.command,
            "passed": result.passed,
            "failed": result.failed,
            "errors": result.errors,
            "skipped": result.skipped,
            "duration_seconds": result.duration_seconds,
            "output": result.output,
        }, indent=2),
        encoding="utf-8",
    )

    logger.info(
        "Tests %s: %d passed, %d failed, %d errors, %d skipped (%.1fs)",
        phase, passed, failed, errors, skipped, duration,
    )
    return result


def load_test_result(increments_dir: str, increment_id: str, phase: str) -> TestResult | None:
    """Load test results from an increment directory."""
    result_file = Path(increments_dir) / increment_id / f"test_{phase}.json"
    if not result_file.exists():
        return None

    data = json.loads(result_file.read_text(encoding="utf-8"))
    return TestResult(
        command=data.get("command", ""),
        passed=data.get("passed", 0),
        failed=data.get("failed", 0),
        errors=data.get("errors", 0),
        skipped=data.get("skipped", 0),
        duration_seconds=data.get("duration_seconds", 0.0),
        output=data.get("output", ""),
    )


def _parse_pytest_output(output: str) -> tuple[int, int, int, int]:
    """Parse pytest summary line for pass/fail/error/skip counts.

    Returns (passed, failed, errors, skipped).
    """
    passed = failed = errors = skipped = 0

    # Match pytest summary like "5 passed, 2 failed, 1 error in 0.05s"
    # or "====== 3 passed in 0.02s ======"
    summary_pattern = re.compile(
        r"=+\s*(.*?)\s+in\s+[\d.]+s\s*=+",
        re.MULTILINE,
    )
    match = summary_pattern.search(output)
    if match:
        summary = match.group(1)
        for part in summary.split(","):
            part = part.strip()
            count_match = re.match(r"(\d+)\s+(\w+)", part)
            if count_match:
                count = int(count_match.group(1))
                label = count_match.group(2).lower()
                if "pass" in label:
                    passed = count
                elif "fail" in label:
                    failed = count
                elif "error" in label:
                    errors = count
                elif "skip" in label or "deselect" in label:
                    skipped = count

    return passed, failed, errors, skipped
