"""Configuration for enrollment processing pipeline.

Python equivalent of 00_config.sas — replaces hard-coded macro variables
and LIBNAME statements with a typed configuration dataclass loaded from YAML.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class EnrollmentConfig:
    """All parameters for the enrollment processing pipeline."""

    # Paths
    data_in: Path = Path("data/input")
    data_out: Path = Path("data/output")
    log_dir: Path = Path("logs")

    # Processing parameters
    start_year: int = 2019
    end_year: int = 2023
    batch_size: int = 10
    total_mods: int = 100
    max_retries: int = 3
    max_workers: int = 10

    # File naming
    in_prefix: str = "enroll_mod_"
    in_suffix: str = ".csv"
    out_prefix: str = "bene_enroll_"

    # CME valid enrollment codes
    valid_buyin: set[str] = field(
        default_factory=lambda: {"0", "1", "2", "3", "A", "B", "C"}
    )
    valid_hmo: set[str] = field(
        default_factory=lambda: {"0", "1", "2", "4", "A", "B", "C"}
    )
    valid_dual: set[str] = field(
        default_factory=lambda: {
            "NA", "00", "01", "02", "03", "04", "05", "06", "08", "09", "10"
        }
    )
    valid_esrd: set[str] = field(
        default_factory=lambda: {"0", "Y", "N"}
    )

    def input_path(self, mod: int) -> Path:
        """Return the CSV input path for a given mod partition."""
        return self.data_in / f"{self.in_prefix}{mod:02d}{self.in_suffix}"

    def output_path(self, mod: int) -> Path:
        """Return the parquet output path for a given mod partition."""
        return self.data_out / f"{self.out_prefix}{mod:02d}.parquet"

    @property
    def year_range(self) -> range:
        return range(self.start_year, self.end_year + 1)

    @property
    def mod_range(self) -> range:
        return range(self.total_mods)
