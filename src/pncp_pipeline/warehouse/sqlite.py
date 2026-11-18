"""SQLite implementations used for local runs and tests.

They mirror the BigQuery Bronze and Control schemas closely enough to exercise
the full pipeline without cloud credentials.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from pncp_pipeline.hashing import canonical_json
from pncp_pipeline.ingestion.records import build_rows
from pncp_pipeline.pncp.models import Page

_SCHEMA = """
CREATE TABLE IF NOT EXISTS bronze_records (
    record_id TEXT PRIMARY KEY,
    ingestion_id TEXT NOT NULL,
    source TEXT NOT NULL,
    entity TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    request_params TEXT NOT NULL,
    page INTEGER NOT NULL,
    record_index INTEGER NOT NULL,
    page_key TEXT NOT NULL,
    gcs_uri TEXT NOT NULL,
    record_hash TEXT NOT NULL,
    source_date TEXT NOT NULL,
    api_status INTEGER NOT NULL,
    payload TEXT NOT NULL,
    ingested_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_bronze_entity_date
    ON bronze_records (entity, source_date);

CREATE TABLE IF NOT EXISTS ingestion_runs (
    run_id TEXT PRIMARY KEY,
    mode TEXT NOT NULL,
    entity TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    status TEXT NOT NULL,
    page_count INTEGER NOT NULL DEFAULT 0,
    record_count INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS ingestion_checkpoints (
    entity TEXT NOT NULL,
    extraction_date TEXT NOT NULL,
    modality INTEGER NOT NULL,
    last_page INTEGER NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (entity, extraction_date, modality)
);

CREATE TABLE IF NOT EXISTS watermarks (
    entity TEXT PRIMARY KEY,
    last_successful_date TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

_INSERT_ROW = """
INSERT OR IGNORE INTO bronze_records (
    record_id, ingestion_id, source, entity, endpoint, request_params,
    page, record_index, page_key, gcs_uri, record_hash, source_date,
    api_status, payload, ingested_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


class SQLiteBronzeLoader:
    """Store Bronze rows in SQLite, deduplicating by record_id."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path, timeout=30)
        self._connection.executescript(_SCHEMA)
        self._connection.commit()

    def load_page(self, page: Page) -> int:
        rows = build_rows(page)
        values = [
            (
                row["record_id"],
                row["ingestion_id"],
                row["source"],
                row["entity"],
                row["endpoint"],
                canonical_json(row["request_params"]),
                row["page"],
                row["record_index"],
                row["page_key"],
                row["gcs_uri"],
                row["record_hash"],
                row["source_date"],
                row["api_status"],
                canonical_json(row["payload"]),
                row["ingested_at"],
            )
            for row in rows
        ]
        before = self._connection.total_changes
        self._connection.executemany(_INSERT_ROW, values)
        self._connection.commit()
        return self._connection.total_changes - before

    def count_records(self, entity: str | None = None) -> int:
        """Return the number of stored records, optionally filtered by entity."""
        if entity is None:
            cursor = self._connection.execute("SELECT COUNT(*) FROM bronze_records")
        else:
            cursor = self._connection.execute(
                "SELECT COUNT(*) FROM bronze_records WHERE entity = ?",
                (entity,),
            )
        return int(cursor.fetchone()[0])

    def close(self) -> None:
        """Close the database connection."""
        self._connection.close()


class SQLiteControlStore:
    """Run history, checkpoints, and watermarks in SQLite."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path, timeout=30)
        self._connection.executescript(_SCHEMA)
        self._connection.commit()

    def start_run(
        self,
        *,
        run_id: str,
        mode: str,
        entity: str,
        start_date: date,
        end_date: date,
    ) -> None:
        self._connection.execute(
            """
            INSERT INTO ingestion_runs (
                run_id, mode, entity, start_date, end_date, status, started_at
            ) VALUES (?, ?, ?, ?, ?, 'running', ?)
            """,
            (
                run_id,
                mode,
                entity,
                start_date.isoformat(),
                end_date.isoformat(),
                datetime.now(tz=UTC).isoformat(),
            ),
        )
        self._connection.commit()

    def finish_run(
        self,
        *,
        run_id: str,
        status: str,
        page_count: int,
        record_count: int,
        error: str | None = None,
    ) -> None:
        self._connection.execute(
            """
            UPDATE ingestion_runs
               SET status = ?, page_count = ?, record_count = ?,
                   finished_at = ?, error_message = ?
             WHERE run_id = ?
            """,
            (
                status,
                page_count,
                record_count,
                datetime.now(tz=UTC).isoformat(),
                error,
                run_id,
            ),
        )
        self._connection.commit()

    def is_day_complete(
        self,
        *,
        entity: str,
        day: date,
        modality: int | None,
    ) -> bool:
        cursor = self._connection.execute(
            """
            SELECT 1 FROM ingestion_checkpoints
             WHERE entity = ? AND extraction_date = ? AND modality = ?
             LIMIT 1
            """,
            (entity, day.isoformat(), _modality_key(modality)),
        )
        return cursor.fetchone() is not None

    def mark_day_complete(
        self,
        *,
        entity: str,
        day: date,
        modality: int | None,
        last_page: int,
    ) -> None:
        self._connection.execute(
            """
            INSERT INTO ingestion_checkpoints (
                entity, extraction_date, modality, last_page, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (entity, extraction_date, modality)
            DO UPDATE SET last_page = excluded.last_page, updated_at = excluded.updated_at
            """,
            (
                entity,
                day.isoformat(),
                _modality_key(modality),
                last_page,
                datetime.now(tz=UTC).isoformat(),
            ),
        )
        self._connection.commit()

    def has_successful_snapshot(self, *, day: date) -> bool:
        cursor = self._connection.execute(
            """
            SELECT 1 FROM ingestion_runs
             WHERE mode = 'snapshot'
               AND status = 'success'
               AND start_date = ?
               AND end_date = ?
             LIMIT 1
            """,
            (day.isoformat(), day.isoformat()),
        )
        return cursor.fetchone() is not None

    def get_watermark(self, *, entity: str) -> date | None:
        cursor = self._connection.execute(
            "SELECT last_successful_date FROM watermarks WHERE entity = ?",
            (entity,),
        )
        row = cursor.fetchone()
        return date.fromisoformat(row[0]) if row else None

    def set_watermark(self, *, entity: str, day: date) -> None:
        self._connection.execute(
            """
            INSERT INTO watermarks (entity, last_successful_date, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT (entity)
            DO UPDATE SET last_successful_date = excluded.last_successful_date,
                          updated_at = excluded.updated_at
            """,
            (entity, day.isoformat(), datetime.now(tz=UTC).isoformat()),
        )
        self._connection.commit()

    def close(self) -> None:
        """Close the database connection."""
        self._connection.close()


def _modality_key(modality: int | None) -> int:
    return 0 if modality is None else modality


def fetch_rows(path: Path, entity: str) -> list[dict[str, Any]]:
    """Test helper: read Bronze rows for an entity from SQLite."""
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        cursor = connection.execute(
            "SELECT * FROM bronze_records WHERE entity = ? ORDER BY record_id",
            (entity,),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        connection.close()
