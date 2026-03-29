"""Generate sample Medicare enrollment CSV files partitioned by BENE_ID mod 100.

Creates small sample files (3 mods: 00, 01, 02) with realistic CMS enrollment
data for testing the legacy SAS codebase and the refactoring framework.
"""

import csv
import os
import random
from pathlib import Path

random.seed(42)

OUTPUT_DIR = Path(__file__).parent / "input"
OUTPUT_DIR.mkdir(exist_ok=True)

# CMS enrollment code value pools
BUYIN_CODES = ["0", "1", "2", "3", "A", "B", "C"]
BUYIN_WEIGHTS = [15, 10, 5, 40, 5, 3, 22]  # '3' and 'C' most common

HMO_CODES = ["0", "1", "2", "4", "A", "B", "C"]
HMO_WEIGHTS = [50, 5, 3, 2, 15, 10, 15]

DUAL_CODES = ["NA", "00", "01", "02", "03", "04", "05", "06", "08", "09", "10"]
DUAL_WEIGHTS = [60, 5, 5, 5, 3, 3, 2, 2, 5, 5, 5]

ESRD_CODES = ["0", "Y", "N"]
ESRD_WEIGHTS = [85, 5, 10]

BIC_CODES = ["A1", "A2", "A3", "B1", "B2", "C1", "C2", "T1", "T2"]
STATE_CODES = ["CA", "TX", "FL", "NY", "PA", "IL", "OH", "GA", "NC", "MI"]
COUNTY_CODES = ["001", "003", "005", "007", "009", "011", "013", "015", "017", "019"]

PTC_CONTRACTS = ["", "", "", "", "H1234", "H5678", "H9012", "H3456"]  # mostly empty
PTD_CONTRACTS = ["", "", "", "S1234", "S5678", "H1111", "R2222", "E3333"]

YEARS = [2019, 2020, 2021, 2022, 2023]
MONTHS = list(range(1, 13))

HEADER = [
    "BENE_ID", "YEAR", "MONTH",
    "MDCR_ENTLMT_BUYIN_IND", "HMO_IND", "DUAL_STUS_CD",
    "PTC_CNTRCT_ID", "PTC_PBP_ID", "PTC_PLAN_TYPE_CD",
    "PTD_CNTRCT_ID", "PTD_PBP_ID", "PTD_SGMT_ID",
    "ESRD_IND", "CRNT_BIC_CD", "STATE_CD", "CNTY_CD",
]

BENES_PER_MOD = 50
MODS_TO_GENERATE = [0, 1, 2]  # just 3 mods for testing


def generate_bene_id(mod: int, seq: int) -> str:
    """Generate a 15-char bene ID whose numeric value mod 100 == mod."""
    base = mod + seq * 100
    return f"{base:015d}"


def generate_monthly_record(bene_id: str, year: int, month: int) -> list[str]:
    """Generate one monthly enrollment record."""
    buyin = random.choices(BUYIN_CODES, weights=BUYIN_WEIGHTS, k=1)[0]
    hmo = random.choices(HMO_CODES, weights=HMO_WEIGHTS, k=1)[0]
    dual = random.choices(DUAL_CODES, weights=DUAL_WEIGHTS, k=1)[0]
    esrd = random.choices(ESRD_CODES, weights=ESRD_WEIGHTS, k=1)[0]
    bic = random.choice(BIC_CODES)
    state = random.choice(STATE_CODES)
    county = random.choice(COUNTY_CODES)

    ptc = random.choice(PTC_CONTRACTS)
    ptc_pbp = f"{random.randint(1, 999):03d}" if ptc else ""
    ptc_type = random.choice(["01", "02", "04", "10", ""]) if ptc else ""

    ptd = random.choice(PTD_CONTRACTS)
    ptd_pbp = f"{random.randint(1, 999):03d}" if ptd else ""
    ptd_sgmt = f"{random.randint(1, 99):03d}" if ptd else ""

    return [
        bene_id, str(year), str(month),
        buyin, hmo, dual,
        ptc, ptc_pbp, ptc_type,
        ptd, ptd_pbp, ptd_sgmt,
        esrd, bic, state, county,
    ]


def main():
    for mod in MODS_TO_GENERATE:
        mod_str = f"{mod:02d}"
        filepath = OUTPUT_DIR / f"enroll_mod_{mod_str}.csv"

        rows = []
        for seq in range(BENES_PER_MOD):
            bene_id = generate_bene_id(mod, seq)

            # Not all benes have all years
            bene_years = random.sample(YEARS, k=random.randint(2, len(YEARS)))

            for year in sorted(bene_years):
                # Most benes have all 12 months; some have gaps
                if random.random() < 0.85:
                    months = MONTHS
                else:
                    months = sorted(random.sample(MONTHS, k=random.randint(6, 11)))

                for month in months:
                    rows.append(generate_monthly_record(bene_id, year, month))

                    # Rare: duplicate row (to test dedup logic)
                    if random.random() < 0.02:
                        rows.append(generate_monthly_record(bene_id, year, month))

        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(HEADER)
            writer.writerows(rows)

        print(f"Generated {filepath.name}: {len(rows)} rows, {BENES_PER_MOD} beneficiaries")


if __name__ == "__main__":
    main()
