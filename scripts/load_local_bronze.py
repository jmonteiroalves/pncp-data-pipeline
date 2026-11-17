"""Replay local Bronze rows into BigQuery.

Useful when the API is throttled: the local SQLite Bronze mirror already holds
validated rows, and this script loads a date range into the cloud Bronze tables.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

from google.cloud import bigquery

from pncp_pipeline.config import get_settings
from pncp_pipeline.warehouse.bigquery import BRONZE_SCHEMA


def _parse_json(value: str | None) -> Any:
    if not value:
        return {}
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {}


def _local_rows(database: Path, start: date, end: date) -> dict[str, list[dict[str, Any]]]:
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    result: dict[str, list[dict[str, Any]]] = {"contratacoes": [], "contratos": []}
    try:
        for entity in result:
            rows = connection.execute(
                """
                SELECT * FROM bronze_records
                 WHERE entity = ?
                   AND source_date BETWEEN ? AND ?
                """,
                (entity, start.isoformat(), end.isoformat()),
            ).fetchall()
            result[entity] = [dict(row) for row in rows]
    finally:
        connection.close()
    return result


def _existing_ids(client: bigquery.Client, project: str, entity: str) -> set[str]:
    sql = f"SELECT record_id FROM `{project}.bronze.pncp_{entity}_raw`"
    return {str(row[0]) for row in client.query(sql).result()}


def _to_bq_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "ingestion_id": row["ingestion_id"],
        "source": "pncp",
        "entity": row["entity"],
        "endpoint": row["endpoint"],
        "request_params": _parse_json(row["request_params"]),
        "page": int(row["page"]),
        "record_index": int(row["record_index"]),
        "page_key": row["page_key"],
        "gcs_uri": row["gcs_uri"],
        "record_id": row["record_id"],
        "record_hash": row["record_hash"],
        "source_date": row["source_date"],
        "api_status": int(row["api_status"]),
        "payload": _parse_json(row["payload"]),
        "ingested_at": row["ingested_at"],
    }


def main() -> int:
    """Load local Bronze rows for a date range into BigQuery."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--database", type=Path, default=Path("data/local.db"))
    parser.add_argument("--batch-size", type=int, default=5_000)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    client = bigquery.Client(project=settings.gcp_project, location=settings.bq_location)
    local = _local_rows(args.database, args.start, args.end)

    for entity, rows in local.items():
        existing = _existing_ids(client, settings.gcp_project, entity)
        new_rows = [_to_bq_row(row) for row in rows if row["record_id"] not in existing]
        print(f"{entity}: local={len(rows)} existing={len(existing)} new={len(new_rows)}")
        if args.dry_run or not new_rows:
            continue

        for start in range(0, len(new_rows), args.batch_size):
            batch = new_rows[start : start + args.batch_size]
            job_config = bigquery.LoadJobConfig(
                schema=list(BRONZE_SCHEMA),
                write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
            )
            client.load_table_from_json(
                batch,
                f"{settings.gcp_project}.bronze.pncp_{entity}_raw",
                job_config=job_config,
                location=settings.bq_location,
            ).result()
            print(f"loaded {len(batch)} rows into bronze.pncp_{entity}_raw")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
