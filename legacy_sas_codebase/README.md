# Legacy SAS Enrollment Processing Codebase

## Overview

SAS-based Medicare beneficiary enrollment processing pipeline, circa 2014. Ingests monthly enrollment CSV files partitioned by beneficiary ID modulo (00-99), validates enrollment codes against CMS Common Medicare Environment (CME) rules, and produces beneficiary-level annual enrollment summaries with concatenated monthly status strings.

## Architecture

```
programs/
├── 00_config.sas           # Global macro vars, paths, libnames, valid code lists
├── 01_enroll_driver.sas    # Parallel batch orchestrator (SYSTASK, 10 mods at a time)
└── 02_enroll_process.sas   # Single-partition processing macro (%PROCESS_ENROLLMENT)
```

## Data Flow

```
Input:  data/input/enroll_mod_XX.csv   (grain: BENE_ID × YEAR × MONTH)
                    │
                    ▼
        ┌──────────────────────┐
        │  PROC IMPORT (CSV)   │
        │  Type coercion       │
        └──────────┬───────────┘
                   ▼
        ┌──────────────────────┐
        │  PROC SORT NODUPKEY  │
        │  Dedup bene×year×mo  │
        └──────────┬───────────┘
                   ▼
        ┌──────────────────────┐
        │  DATA step validate  │
        │  CME code rules      │
        └──────────┬───────────┘
                   ▼
        ┌──────────────────────┐
        │  12-month skeleton   │
        │  fill + LEFT JOIN    │
        └──────────┬───────────┘
                   ▼
        ┌──────────────────────┐
        │  DATA step RETAIN    │
        │  Concatenate monthly │
        │  → annual strings    │
        └──────────┬───────────┘
                   ▼
Output: data/output/bene_enroll_XX.sas7bdat  (grain: BENE_ID × YEAR)
```

## Parallel Execution

The driver (`01_enroll_driver.sas`) processes 100 partitions in batches of 10:
- Generates a temporary .sas file per mod that re-establishes config
- Launches via `SYSTASK COMMAND` (spawns child SAS sessions)
- `WAITFOR _ALL_` synchronizes each batch
- Failed partitions retry up to 3 times sequentially
- Post-batch QA checks: duplicate detection, string length validation, month count bounds

## Output Schema

| Column | Type | Description |
|--------|------|-------------|
| BENE_ID | char(15) | Beneficiary identifier |
| YEAR | num | Enrollment year |
| BENE_MDCR_BUYIN_IND | char(12) | Monthly buy-in indicators Jan-Dec (e.g., "3333CCCCCCCC") |
| BENE_HMO_IND | char(12) | Monthly HMO indicators Jan-Dec |
| BENE_DUAL_STUS_CD | char(24) | Monthly dual status codes (2 chars/month) |
| BENE_ESRD_IND | char(12) | Monthly ESRD indicators Jan-Dec |
| BENE_PTC_CNTRCT_01-12 | char(5) | Part C contract ID per month |
| BENE_PTD_CNTRCT_01-12 | char(5) | Part D contract ID per month |
| BENE_STATE_CD | char(2) | Last known state FIPS |
| BENE_CNTY_CD | char(3) | Last known county FIPS |
| BENE_CRNT_BIC_CD | char(2) | Current beneficiary ID code |
| ENRL_SRC_MOD | char(2) | Source partition (00-99) |
| MONTHS_ENROLLED | num | Count of entitled months |

## Sample Data

Run `python data/generate_sample_data.py` to generate 3 sample partitions (mods 00-02) with 50 beneficiaries each across 2019-2023.
