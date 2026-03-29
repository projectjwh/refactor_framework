"""Parallel batch driver for enrollment processing.

Python equivalent of 01_enroll_driver.sas. Replaces:
  - SYSTASK + WAITFOR parallel execution -> concurrent.futures.ProcessPoolExecutor
  - Generated child .sas files -> direct function calls
  - %DO %WHILE batch loop -> executor.map()
  - PROC SQL QA checks -> Polars-based validation
  - Cross-partition duplicate check via UNION ALL view -> Polars scan + group_by
"""

from __future__ import annotations

import logging
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import polars as pl

from config import EnrollmentConfig
from enroll_process import process_partition

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("enrollment.driver")


def run_all_partitions(cfg: EnrollmentConfig) -> list[dict]:
    """Process all mod partitions with parallel execution.

    Partitions are submitted to a process pool (max_workers at a time).
    Failed partitions are retried sequentially up to max_retries.
    """
    logger.info(
        "Starting enrollment processing: mods 00-%02d, years %d-%d, workers=%d",
        cfg.total_mods - 1, cfg.start_year, cfg.end_year, cfg.max_workers,
    )
    start = time.perf_counter()
    results = []

    # --- Phase 1: Parallel execution ---
    with ProcessPoolExecutor(max_workers=cfg.max_workers) as pool:
        futures = {
            pool.submit(process_partition, mod, cfg): mod
            for mod in cfg.mod_range
            if cfg.input_path(mod).exists()
        }

        for future in as_completed(futures):
            mod = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as exc:
                logger.error("MOD %02d failed: %s", mod, exc)
                results.append({"mod": mod, "status": "FAILED", "n_records": 0})

    # --- Phase 2: Retry failures sequentially ---
    failed_mods = [r["mod"] for r in results if r["status"] == "FAILED"]

    for retry in range(1, cfg.max_retries + 1):
        if not failed_mods:
            break
        logger.warning("Retry %d for %d failed mods: %s", retry, len(failed_mods), failed_mods)
        still_failed = []
        for mod in failed_mods:
            try:
                result = process_partition(mod, cfg)
                results = [r for r in results if r["mod"] != mod]
                results.append(result)
            except Exception as exc:
                logger.error("Retry %d MOD %02d failed: %s", retry, mod, exc)
                still_failed.append(mod)
        failed_mods = still_failed

    # --- Phase 3: QA checks ---
    qa_results = run_qa_checks(cfg, results)

    # --- Summary ---
    duration = time.perf_counter() - start
    _print_summary(results, qa_results, duration)

    return results


def run_qa_checks(cfg: EnrollmentConfig, results: list[dict]) -> dict:
    """Post-processing QA: duplicate checks, string length validation."""
    qa = {"duplicates": 0, "invalid_buyin_len": 0, "invalid_months": 0, "cross_partition": 0}

    successful_mods = [r["mod"] for r in results if r["status"] == "SUCCESS"]
    if not successful_mods:
        return qa

    for mod in successful_mods:
        outfile = cfg.output_path(mod)
        if not outfile.exists():
            continue

        df = pl.read_parquet(outfile)

        # Check: no duplicate BENE_ID x YEAR
        dups = df.group_by("BENE_ID", "YEAR").len().filter(pl.col("len") > 1)
        if len(dups) > 0:
            logger.error("QA FAIL: MOD %02d has %d duplicate BENE_ID x YEAR", mod, len(dups))
            qa["duplicates"] += len(dups)

        # Check: BUYIN string should be exactly 12 chars
        bad_len = df.filter(pl.col("BENE_MDCR_BUYIN_IND").str.len_chars() != 12)
        if len(bad_len) > 0:
            logger.warning("QA: MOD %02d has %d rows with BUYIN length != 12", mod, len(bad_len))
            qa["invalid_buyin_len"] += len(bad_len)

        # Check: MONTHS_ENROLLED between 0 and 12
        bad_months = df.filter(
            (pl.col("MONTHS_ENROLLED") < 0) | (pl.col("MONTHS_ENROLLED") > 12)
        )
        if len(bad_months) > 0:
            logger.error("QA FAIL: MOD %02d has %d invalid MONTHS_ENROLLED", mod, len(bad_months))
            qa["invalid_months"] += len(bad_months)

    # Cross-partition duplicate check
    frames = []
    for mod in successful_mods:
        outfile = cfg.output_path(mod)
        if outfile.exists():
            frames.append(
                pl.read_parquet(outfile, columns=["BENE_ID", "YEAR", "ENRL_SRC_MOD"])
            )

    if frames:
        all_enroll = pl.concat(frames)
        cross_dups = (
            all_enroll.group_by("BENE_ID", "YEAR")
            .agg(pl.col("ENRL_SRC_MOD").n_unique().alias("n_mods"))
            .filter(pl.col("n_mods") > 1)
        )
        if len(cross_dups) > 0:
            logger.error(
                "CROSS-PARTITION DUPLICATES: %d bene-years in multiple mods", len(cross_dups)
            )
            qa["cross_partition"] = len(cross_dups)
        else:
            logger.info("Cross-partition check PASSED")

    return qa


def _print_summary(results: list[dict], qa: dict, duration: float) -> None:
    """Print processing summary."""
    success = sum(1 for r in results if r["status"] == "SUCCESS")
    failed = sum(1 for r in results if r["status"] == "FAILED")
    skipped = sum(1 for r in results if r["status"] == "SKIPPED")
    total_records = sum(r.get("n_records", 0) for r in results)

    logger.info("=" * 60)
    logger.info("ENROLLMENT PROCESSING COMPLETE")
    logger.info("  Success: %d | Failed: %d | Skipped: %d", success, failed, skipped)
    logger.info("  Total bene-year records: %d", total_records)
    logger.info("  QA issues: %s", {k: v for k, v in qa.items() if v > 0} or "none")
    logger.info("  Duration: %.1fs", duration)
    logger.info("=" * 60)


if __name__ == "__main__":
    cfg = EnrollmentConfig(
        data_in=Path("../data/input"),
        data_out=Path("../data/output"),
    )
    run_all_partitions(cfg)
