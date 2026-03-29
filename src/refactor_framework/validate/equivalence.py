"""Behavioral equivalence testing — compare outputs from source and target pipelines.

Compares data outputs (CSV, Parquet) row-by-row and column-by-column to verify
that the Python migration produces the same results as the SAS original.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger("refactor_framework.validate")

# Supported formats for comparison
_READERS = {}


def _ensure_polars():
    """Lazy import polars — only needed for validate command."""
    try:
        import polars as pl
        return pl
    except ImportError:
        raise ImportError(
            "polars is required for equivalence testing. Install with: pip install polars"
        )


def compare_outputs(
    source_path: Path,
    target_path: Path,
    key_columns: list[str],
    tolerance: float = 0.0,
    max_diffs: int = 50,
) -> dict:
    """Compare two data files and return a diff report.

    Parameters
    ----------
    source_path : Path to the source output (SAS .csv, .sas7bdat, .parquet)
    target_path : Path to the target output (Python .csv, .parquet)
    key_columns : Column names forming the join key
    tolerance : Numeric tolerance for float comparisons
    max_diffs : Maximum number of row-level diffs to report

    Returns
    -------
    dict with: match (bool), summary, column_diffs, row_diffs, missing_rows
    """
    pl = _ensure_polars()

    src = _read_file(pl, source_path)
    tgt = _read_file(pl, target_path)

    result = {
        "source_file": str(source_path),
        "target_file": str(target_path),
        "source_rows": len(src),
        "target_rows": len(tgt),
        "match": True,
        "column_diffs": [],
        "row_diffs": [],
        "missing_in_target": 0,
        "missing_in_source": 0,
        "summary": "",
    }

    # Column comparison
    src_cols = set(src.columns)
    tgt_cols = set(tgt.columns)
    only_in_source = sorted(src_cols - tgt_cols)
    only_in_target = sorted(tgt_cols - src_cols)
    common_cols = sorted(src_cols & tgt_cols)

    if only_in_source:
        result["column_diffs"].append({"type": "only_in_source", "columns": only_in_source})
        result["match"] = False
    if only_in_target:
        result["column_diffs"].append({"type": "only_in_target", "columns": only_in_target})

    # Standardize column names for join
    for col in key_columns:
        if col not in src.columns or col not in tgt.columns:
            result["match"] = False
            result["summary"] = f"Key column '{col}' missing from one or both files"
            return result

    # Cast key columns to string for safe join
    for col in key_columns:
        src = src.with_columns(pl.col(col).cast(pl.Utf8).alias(col))
        tgt = tgt.with_columns(pl.col(col).cast(pl.Utf8).alias(col))

    # Count rows in each that aren't in the other
    src_keys = src.select(key_columns)
    tgt_keys = tgt.select(key_columns)
    missing_in_target = src_keys.join(tgt_keys, on=key_columns, how="anti")
    missing_in_source = tgt_keys.join(src_keys, on=key_columns, how="anti")

    result["missing_in_target"] = len(missing_in_target)
    result["missing_in_source"] = len(missing_in_source)

    if result["missing_in_target"] > 0 or result["missing_in_source"] > 0:
        result["match"] = False

    # Value comparison on common columns (for matched rows)
    matched = src.join(tgt, on=key_columns, how="inner", suffix="_tgt")
    value_cols = [c for c in common_cols if c not in key_columns]
    diff_count = 0

    for col in value_cols:
        tgt_col = f"{col}_tgt"
        if tgt_col not in matched.columns:
            continue

        # Compare values
        mismatches = matched.filter(
            pl.col(col).cast(pl.Utf8).fill_null("NULL")
            != pl.col(tgt_col).cast(pl.Utf8).fill_null("NULL")
        )

        if len(mismatches) > 0:
            result["match"] = False
            diff_count += len(mismatches)
            # Sample some diffs
            sample = mismatches.head(min(5, len(mismatches)))
            for row in sample.iter_rows(named=True):
                if len(result["row_diffs"]) < max_diffs:
                    key_vals = {k: row[k] for k in key_columns}
                    result["row_diffs"].append({
                        "key": key_vals,
                        "column": col,
                        "source_value": str(row[col]),
                        "target_value": str(row[tgt_col]),
                    })

    # Summary
    if result["match"]:
        result["summary"] = (
            f"MATCH: {len(src)} rows, {len(common_cols)} columns — all values identical"
        )
    else:
        parts = []
        if result["missing_in_target"]:
            parts.append(f"{result['missing_in_target']} rows missing in target")
        if result["missing_in_source"]:
            parts.append(f"{result['missing_in_source']} extra rows in target")
        if diff_count:
            parts.append(f"{diff_count} value mismatches")
        if only_in_source:
            parts.append(f"{len(only_in_source)} columns only in source")
        result["summary"] = "MISMATCH: " + "; ".join(parts)

    return result


def compare_to_report(result: dict, output_path: Path) -> None:
    """Write an equivalence comparison result to a JSON report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, default=str),
        encoding="utf-8",
    )
    logger.info("Equivalence report: %s -> %s", result["summary"], output_path)


def _read_file(pl, path: Path):
    """Read a data file into a Polars DataFrame."""
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pl.read_parquet(path)
    elif suffix == ".csv":
        return pl.read_csv(path, infer_schema_length=10000)
    elif suffix in (".sas7bdat",):
        # Requires pyreadstat
        try:
            import pyreadstat
            df, _ = pyreadstat.read_sas7bdat(str(path))
            return pl.from_pandas(df)
        except ImportError:
            raise ImportError("pyreadstat required for .sas7bdat files")
    else:
        raise ValueError(f"Unsupported file format: {suffix}")
