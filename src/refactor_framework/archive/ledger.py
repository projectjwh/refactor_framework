"""Persistent ledger for increment records (JSON and SQLite backends)."""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import asdict
from pathlib import Path

from refactor_framework.models import IncrementRecord
from refactor_framework.utils.paths import ensure_dir

logger = logging.getLogger("refactor_framework.archive")


class Ledger:
    """Persistence layer for increment records."""

    def __init__(self, path: str, backend: str = "json"):
        self._path = Path(path)
        self._backend = backend
        ensure_dir(self._path.parent)

        if backend == "sqlite":
            self._init_sqlite()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def append(self, record: IncrementRecord) -> None:
        """Append or upsert an increment record."""
        if self._backend == "sqlite":
            self._sqlite_upsert(record)
        else:
            self._json_upsert(record)
        logger.info("Ledger updated: %s (%s)", record.increment_id, record.status)

    def get(self, increment_id: str) -> IncrementRecord | None:
        """Retrieve a single record by increment ID."""
        if self._backend == "sqlite":
            return self._sqlite_get(increment_id)
        return self._json_get(increment_id)

    def list_all(self) -> list[IncrementRecord]:
        """Return all records sorted by increment ID."""
        if self._backend == "sqlite":
            return self._sqlite_list_all()
        return self._json_list_all()

    # ------------------------------------------------------------------
    # JSON backend
    # ------------------------------------------------------------------

    def _json_load(self) -> list[dict]:
        if not self._path.exists():
            return []
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, ValueError):
            return []

    def _json_save(self, records: list[dict]) -> None:
        self._path.write_text(
            json.dumps(records, indent=2, default=str),
            encoding="utf-8",
        )

    def _json_upsert(self, record: IncrementRecord) -> None:
        records = self._json_load()
        data = asdict(record)
        # Replace existing or append
        for i, r in enumerate(records):
            if r.get("increment_id") == record.increment_id:
                records[i] = data
                self._json_save(records)
                return
        records.append(data)
        self._json_save(records)

    def _json_get(self, increment_id: str) -> IncrementRecord | None:
        for r in self._json_load():
            if r.get("increment_id") == increment_id:
                return _dict_to_record(r)
        return None

    def _json_list_all(self) -> list[IncrementRecord]:
        records = [_dict_to_record(r) for r in self._json_load()]
        records.sort(key=lambda r: r.increment_id)
        return records

    # ------------------------------------------------------------------
    # SQLite backend
    # ------------------------------------------------------------------

    def _init_sqlite(self) -> None:
        conn = sqlite3.connect(str(self._path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS increments (
                increment_id TEXT PRIMARY KEY,
                data TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    def _sqlite_upsert(self, record: IncrementRecord) -> None:
        conn = sqlite3.connect(str(self._path))
        data_json = json.dumps(asdict(record), default=str)
        conn.execute(
            "INSERT OR REPLACE INTO increments (increment_id, data) VALUES (?, ?)",
            (record.increment_id, data_json),
        )
        conn.commit()
        conn.close()

    def _sqlite_get(self, increment_id: str) -> IncrementRecord | None:
        conn = sqlite3.connect(str(self._path))
        row = conn.execute(
            "SELECT data FROM increments WHERE increment_id = ?", (increment_id,)
        ).fetchone()
        conn.close()
        if row:
            return _dict_to_record(json.loads(row[0]))
        return None

    def _sqlite_list_all(self) -> list[IncrementRecord]:
        conn = sqlite3.connect(str(self._path))
        rows = conn.execute(
            "SELECT data FROM increments ORDER BY increment_id"
        ).fetchall()
        conn.close()
        return [_dict_to_record(json.loads(row[0])) for row in rows]


def _dict_to_record(d: dict) -> IncrementRecord:
    """Reconstruct an IncrementRecord from a dict."""
    from refactor_framework.models import (
        ConstructMapping,
        EfficiencyMetrics,
        FileMetrics,
        IncrementPlan,
        IncrementSnapshot,
        MigrationConfig,
        TestResult,
        TimeRecord,
        TokenUsage,
    )

    def _build_snapshot(data: dict | None) -> IncrementSnapshot | None:
        if data is None:
            return None
        files = [FileMetrics(**f) for f in data.get("files", [])]
        return IncrementSnapshot(
            phase=data.get("phase", ""),
            timestamp=data.get("timestamp", ""),
            files=files,
            total_loc=data.get("total_loc", 0),
            avg_complexity=data.get("avg_complexity", 0.0),
            avg_maintainability=data.get("avg_maintainability", 0.0),
        )

    def _build_test(data: dict | None) -> TestResult | None:
        if data is None:
            return None
        return TestResult(**{k: v for k, v in data.items()})

    def _build_plan(data: dict) -> IncrementPlan:
        mappings_raw = data.pop("construct_mappings", [])
        migration_raw = data.pop("migration", {})
        plan = IncrementPlan(**{k: v for k, v in data.items()})
        plan.construct_mappings = [ConstructMapping(**m) for m in mappings_raw]
        if migration_raw:
            plan.migration = MigrationConfig(**migration_raw)
        return plan

    plan = _build_plan(dict(d.get("plan", {})))

    tu_data = d.get("token_usage", {})
    token_usage = TokenUsage(**{k: v for k, v in tu_data.items()})

    tr_data = d.get("time_record", {})
    time_record = TimeRecord(**{k: v for k, v in tr_data.items()})

    eff_data = d.get("efficiency", {})
    efficiency = EfficiencyMetrics(**{k: v for k, v in eff_data.items()})

    return IncrementRecord(
        increment_id=d.get("increment_id", ""),
        status=d.get("status", "planned"),
        plan=plan,
        before=_build_snapshot(d.get("before")),
        after=_build_snapshot(d.get("after")),
        token_usage=token_usage,
        time_record=time_record,
        test_before=_build_test(d.get("test_before")),
        test_after=_build_test(d.get("test_after")),
        efficiency=efficiency,
        diff_summary=d.get("diff_summary", {}),
    )
