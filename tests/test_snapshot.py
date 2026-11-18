"""Tests for monthly snapshot dates and guards."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from pncp_pipeline.cli import main
from pncp_pipeline.snapshot import first_tuesday, snapshot_day_for
from pncp_pipeline.warehouse.sqlite import SQLiteControlStore


def test_first_tuesday_of_january_2026() -> None:
    assert first_tuesday(date(2026, 1, 14)) == date(2026, 1, 6)


def test_first_tuesday_when_month_starts_on_tuesday() -> None:
    assert first_tuesday(date(2026, 9, 20)) == date(2026, 9, 1)


def test_snapshot_day_is_stable_across_the_month() -> None:
    assert snapshot_day_for(date(2026, 2, 1)) == date(2026, 2, 3)
    assert snapshot_day_for(date(2026, 2, 27)) == date(2026, 2, 3)


def test_snapshot_cli_skips_future_date(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["snapshot", "--date", "2099-01-01"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "skipped"
    assert "future" in payload["reason"]


def test_sqlite_has_successful_snapshot(tmp_path: Path) -> None:
    store = SQLiteControlStore(tmp_path / "control.db")
    day = date(2026, 1, 6)
    assert not store.has_successful_snapshot(day=day)

    store.start_run(
        run_id="run-1",
        mode="snapshot",
        entity="contratacoes,contratos",
        start_date=day,
        end_date=day,
    )
    store.finish_run(run_id="run-1", status="success", page_count=1, record_count=1)

    assert store.has_successful_snapshot(day=day)
    store.close()
