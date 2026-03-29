"""Tests for ledger persistence."""

from __future__ import annotations

from pathlib import Path

from refactor_framework.archive.ledger import Ledger
from refactor_framework.models import IncrementPlan, IncrementRecord, TokenUsage


def _make_record(inc_id: str, status: str = "planned") -> IncrementRecord:
    return IncrementRecord(
        increment_id=inc_id,
        status=status,
        plan=IncrementPlan(increment_id=inc_id, description=f"Test {inc_id}"),
        token_usage=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150),
    )


class TestJsonLedger:
    def test_append_and_get(self, tmp_path: Path):
        ledger = Ledger(str(tmp_path / "ledger.json"), backend="json")
        record = _make_record("20260326T100000")

        ledger.append(record)
        retrieved = ledger.get("20260326T100000")

        assert retrieved is not None
        assert retrieved.increment_id == "20260326T100000"
        assert retrieved.token_usage.total_tokens == 150

    def test_upsert_updates_existing(self, tmp_path: Path):
        ledger = Ledger(str(tmp_path / "ledger.json"), backend="json")
        ledger.append(_make_record("20260326T100000", status="planned"))
        ledger.append(_make_record("20260326T100000", status="reported"))

        retrieved = ledger.get("20260326T100000")
        assert retrieved.status == "reported"

        # Should still be only one record
        assert len(ledger.list_all()) == 1

    def test_list_all_sorted(self, tmp_path: Path):
        ledger = Ledger(str(tmp_path / "ledger.json"), backend="json")
        ledger.append(_make_record("20260326T120000"))
        ledger.append(_make_record("20260326T100000"))
        ledger.append(_make_record("20260326T110000"))

        records = ledger.list_all()
        ids = [r.increment_id for r in records]
        assert ids == ["20260326T100000", "20260326T110000", "20260326T120000"]

    def test_get_nonexistent_returns_none(self, tmp_path: Path):
        ledger = Ledger(str(tmp_path / "ledger.json"), backend="json")
        assert ledger.get("nonexistent") is None

    def test_empty_ledger_list(self, tmp_path: Path):
        ledger = Ledger(str(tmp_path / "ledger.json"), backend="json")
        assert ledger.list_all() == []


class TestSqliteLedger:
    def test_append_and_get(self, tmp_path: Path):
        ledger = Ledger(str(tmp_path / "ledger.db"), backend="sqlite")
        record = _make_record("20260326T100000")

        ledger.append(record)
        retrieved = ledger.get("20260326T100000")

        assert retrieved is not None
        assert retrieved.increment_id == "20260326T100000"
        assert retrieved.token_usage.total_tokens == 150

    def test_upsert_updates_existing(self, tmp_path: Path):
        ledger = Ledger(str(tmp_path / "ledger.db"), backend="sqlite")
        ledger.append(_make_record("20260326T100000", status="planned"))
        ledger.append(_make_record("20260326T100000", status="archived"))

        retrieved = ledger.get("20260326T100000")
        assert retrieved.status == "archived"
        assert len(ledger.list_all()) == 1

    def test_list_all_sorted(self, tmp_path: Path):
        ledger = Ledger(str(tmp_path / "ledger.db"), backend="sqlite")
        ledger.append(_make_record("20260326T120000"))
        ledger.append(_make_record("20260326T100000"))

        records = ledger.list_all()
        ids = [r.increment_id for r in records]
        assert ids == ["20260326T100000", "20260326T120000"]

    def test_get_nonexistent_returns_none(self, tmp_path: Path):
        ledger = Ledger(str(tmp_path / "ledger.db"), backend="sqlite")
        assert ledger.get("nonexistent") is None
