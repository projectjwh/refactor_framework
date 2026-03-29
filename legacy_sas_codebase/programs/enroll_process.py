"""Single-partition enrollment processing.

Python equivalent of 02_enroll_process.sas %PROCESS_ENROLLMENT macro.
Replaces: PROC IMPORT, PROC SORT NODUPKEY, DATA step RETAIN/SUBSTR
    concatenation, brute-force IF/ELSE, skeleton LEFT JOIN.
With:     Polars read_csv, .unique(), .group_by().agg() with vectorized
    string building — single pass, no temp datasets.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import polars as pl

from config import EnrollmentConfig

logger = logging.getLogger("enrollment.process")

# Columns to read and their target types
INPUT_SCHEMA = {
    "BENE_ID": pl.Utf8,
    "YEAR": pl.Int32,
    "MONTH": pl.Int32,
    "MDCR_ENTLMT_BUYIN_IND": pl.Utf8,
    "HMO_IND": pl.Utf8,
    "DUAL_STUS_CD": pl.Utf8,
    "PTC_CNTRCT_ID": pl.Utf8,
    "PTD_CNTRCT_ID": pl.Utf8,
    "ESRD_IND": pl.Utf8,
    "CRNT_BIC_CD": pl.Utf8,
    "STATE_CD": pl.Utf8,
    "CNTY_CD": pl.Utf8,
}

# Default fill values for missing months
DEFAULTS = {
    "MDCR_ENTLMT_BUYIN_IND": "0",
    "HMO_IND": "0",
    "DUAL_STUS_CD": "NA",
    "PTC_CNTRCT_ID": "",
    "PTD_CNTRCT_ID": "",
    "ESRD_IND": "0",
    "CRNT_BIC_CD": "",
    "STATE_CD": "",
    "CNTY_CD": "",
}


def process_partition(mod: int, cfg: EnrollmentConfig) -> dict:
    """Process a single mod partition end-to-end.

    Returns a dict with: mod, n_records, n_dups_removed, duration_s.
    """
    start = time.perf_counter()
    infile = cfg.input_path(mod)

    if not infile.exists():
        logger.error("Input file not found: %s", infile)
        return {"mod": mod, "status": "SKIPPED", "n_records": 0}

    logger.info("MOD %02d: reading %s", mod, infile.name)

    # --- Step 1: Ingest CSV with type enforcement ---
    df = pl.read_csv(
        infile,
        schema_overrides=INPUT_SCHEMA,
        null_values=["", " "],
    )

    # Standardize: uppercase, strip whitespace
    str_cols = [c for c, t in INPUT_SCHEMA.items() if t == pl.Utf8]
    df = df.with_columns(
        pl.col(c).str.strip_chars().str.to_uppercase() for c in str_cols
    )

    # Filter invalid year/month
    df = df.filter(
        pl.col("MONTH").is_between(1, 12)
        & pl.col("YEAR").is_between(2000, 2099)
    )

    n_raw = len(df)

    # --- Step 2: Deduplicate on BENE_ID x YEAR x MONTH ---
    df = df.unique(subset=["BENE_ID", "YEAR", "MONTH"], keep="last")
    n_dups = n_raw - len(df)
    if n_dups > 0:
        logger.warning("MOD %02d: removed %d duplicate bene-month rows", mod, n_dups)

    # --- Step 3: Validate enrollment codes ---
    df = _validate_codes(df, cfg)

    # --- Step 4: Fill missing months (ensure 12 per bene-year) ---
    df = _fill_missing_months(df)

    # --- Step 5: Concatenate monthly codes into annual strings ---
    annual = _build_annual_strings(df, mod)

    # --- Step 6: Write output ---
    outfile = cfg.output_path(mod)
    outfile.parent.mkdir(parents=True, exist_ok=True)
    annual.write_parquet(outfile)

    duration = time.perf_counter() - start
    n_benes = len(annual)
    logger.info("MOD %02d: %d bene-years written in %.1fs", mod, n_benes, duration)

    return {
        "mod": mod,
        "status": "SUCCESS",
        "n_records": n_benes,
        "n_dups_removed": n_dups,
        "duration_s": round(duration, 2),
    }


def _validate_codes(df: pl.DataFrame, cfg: EnrollmentConfig) -> pl.DataFrame:
    """Validate enrollment codes against CME rules, defaulting invalid values."""
    return df.with_columns(
        pl.when(pl.col("MDCR_ENTLMT_BUYIN_IND").is_in(cfg.valid_buyin))
        .then(pl.col("MDCR_ENTLMT_BUYIN_IND"))
        .otherwise(pl.lit("0"))
        .alias("MDCR_ENTLMT_BUYIN_IND"),
        pl.when(pl.col("HMO_IND").is_in(cfg.valid_hmo))
        .then(pl.col("HMO_IND"))
        .otherwise(pl.lit("0"))
        .alias("HMO_IND"),
        pl.when(pl.col("DUAL_STUS_CD").is_in(cfg.valid_dual))
        .then(pl.col("DUAL_STUS_CD"))
        .otherwise(pl.lit("NA"))
        .alias("DUAL_STUS_CD"),
        pl.when(pl.col("ESRD_IND").is_in(cfg.valid_esrd))
        .then(pl.col("ESRD_IND"))
        .otherwise(pl.lit("0"))
        .alias("ESRD_IND"),
    )


def _fill_missing_months(df: pl.DataFrame) -> pl.DataFrame:
    """Ensure every bene-year has exactly 12 month rows."""
    bene_years = df.select("BENE_ID", "YEAR").unique()
    months = pl.DataFrame({"MONTH": list(range(1, 13))})
    skeleton = bene_years.join(months, how="cross")

    filled = skeleton.join(
        df, on=["BENE_ID", "YEAR", "MONTH"], how="left"
    )

    for col_name, default_val in DEFAULTS.items():
        if col_name in filled.columns:
            filled = filled.with_columns(
                pl.col(col_name).fill_null(pl.lit(default_val))
            )

    return filled.sort("BENE_ID", "YEAR", "MONTH")


def _build_annual_strings(df: pl.DataFrame, mod: int) -> pl.DataFrame:
    """Aggregate monthly rows into one row per bene-year with concatenated strings.

    Replaces the SAS RETAIN + SUBSTR + 24-line IF/ELSE pattern with a single
    Polars group_by().agg() call using sort_by + str.concat.
    """
    df = df.sort("BENE_ID", "YEAR", "MONTH")

    annual = df.group_by("BENE_ID", "YEAR", maintain_order=True).agg(
        # 1-char-per-month concatenated strings (12 chars each)
        pl.col("MDCR_ENTLMT_BUYIN_IND")
        .sort_by("MONTH")
        .str.concat("")
        .alias("BENE_MDCR_BUYIN_IND"),
        pl.col("HMO_IND")
        .sort_by("MONTH")
        .str.concat("")
        .alias("BENE_HMO_IND"),
        pl.col("ESRD_IND")
        .sort_by("MONTH")
        .str.concat("")
        .alias("BENE_ESRD_IND"),
        # 2-char-per-month concatenated string (24 chars)
        pl.col("DUAL_STUS_CD")
        .sort_by("MONTH")
        .str.concat("")
        .alias("BENE_DUAL_STUS_CD"),
        # Per-month contract IDs (replaces BENE_PTC_CNTRCT_01 through _12)
        *[
            pl.col("PTC_CNTRCT_ID")
            .sort_by("MONTH")
            .get(i)
            .alias(f"BENE_PTC_CNTRCT_{i + 1:02d}")
            for i in range(12)
        ],
        *[
            pl.col("PTD_CNTRCT_ID")
            .sort_by("MONTH")
            .get(i)
            .alias(f"BENE_PTD_CNTRCT_{i + 1:02d}")
            for i in range(12)
        ],
        # Last known geo and BIC
        pl.col("STATE_CD")
        .filter(pl.col("STATE_CD") != "")
        .last()
        .alias("BENE_STATE_CD"),
        pl.col("CNTY_CD")
        .filter(pl.col("CNTY_CD") != "")
        .last()
        .alias("BENE_CNTY_CD"),
        pl.col("CRNT_BIC_CD")
        .filter(pl.col("CRNT_BIC_CD") != "")
        .last()
        .alias("BENE_CRNT_BIC_CD"),
        # Months enrolled: count where BUYIN != '0'
        (pl.col("MDCR_ENTLMT_BUYIN_IND") != "0")
        .sum()
        .alias("MONTHS_ENROLLED"),
    )

    return annual.with_columns(
        pl.lit(f"{mod:02d}").alias("ENRL_SRC_MOD")
    ).sort("BENE_ID", "YEAR")
