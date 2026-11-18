"""BigQuery Bronze loader and control store."""

from __future__ import annotations

from datetime import date
from typing import Any

from google.cloud import bigquery

from pncp_pipeline.ingestion.records import build_rows
from pncp_pipeline.pncp.models import Page
from pncp_pipeline.warehouse.sql import bronze_merge_sql, bronze_table_ddl, control_ddl

BRONZE_SCHEMA: tuple[bigquery.SchemaField, ...] = (
    bigquery.SchemaField("ingestion_id", "STRING"),
    bigquery.SchemaField("source", "STRING"),
    bigquery.SchemaField("entity", "STRING"),
    bigquery.SchemaField("endpoint", "STRING"),
    bigquery.SchemaField("request_params", "JSON"),
    bigquery.SchemaField("page", "INT64"),
    bigquery.SchemaField("record_index", "INT64"),
    bigquery.SchemaField("page_key", "STRING"),
    bigquery.SchemaField("gcs_uri", "STRING"),
    bigquery.SchemaField("record_id", "STRING"),
    bigquery.SchemaField("record_hash", "STRING"),
    bigquery.SchemaField("source_date", "DATE"),
    bigquery.SchemaField("api_status", "INT64"),
    bigquery.SchemaField("payload", "JSON"),
    bigquery.SchemaField("ingested_at", "TIMESTAMP"),
)


class BigQueryBronzeLoader:
    """Load pages into BigQuery and MERGE by source date and record id."""

    def __init__(self, project: str, dataset: str, location: str = "US") -> None:
        self._client = bigquery.Client(project=project, location=location)
        self._project = project
        self._dataset = dataset
        self._location = location

    def ensure_tables(self) -> None:
        """Create the Bronze tables if they do not exist."""
        for entity in ("contratacoes", "contratos"):
            self._client.query(bronze_table_ddl(self._target(entity))).result()

    def load_page(self, page: Page) -> int:
        rows = build_rows(page)
        if not rows:
            return 0

        staging = self._staging(page.entity)
        job_config = bigquery.LoadJobConfig(
            schema=list(BRONZE_SCHEMA),
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        )
        job = self._client.load_table_from_json(
            rows,
            staging,
            job_config=job_config,
            location=self._location,
        )
        job.result()
        self._client.query(
            bronze_merge_sql(self._target(page.entity), staging),
            location=self._location,
        ).result()
        return len(rows)

    def close(self) -> None:
        """Close the BigQuery client."""
        self._client.close()  # type: ignore[no-untyped-call]

    def _target(self, entity: str) -> str:
        return f"{self._project}.{self._dataset}.pncp_{entity}_raw"

    def _staging(self, entity: str) -> str:
        return f"{self._project}.{self._dataset}._staging_{entity}"


class BigQueryControlStore:
    """Control tables backed by BigQuery."""

    def __init__(self, project: str, dataset: str, location: str = "US") -> None:
        self._client = bigquery.Client(project=project, location=location)
        self._dataset = f"{project}.{dataset}"
        self._location = location

    def ensure_tables(self) -> None:
        """Create the control tables if they do not exist."""
        self._client.query(control_ddl(self._dataset)).result()

    def start_run(
        self,
        *,
        run_id: str,
        mode: str,
        entity: str,
        start_date: date,
        end_date: date,
    ) -> None:
        self._query(
            f"""
            INSERT INTO `{self._dataset}.ingestion_runs` (
                run_id, mode, entity, start_date, end_date, status,
                page_count, record_count, started_at
            ) VALUES (
                @run_id, @mode, @entity, @start_date, @end_date, 'running',
                0, 0, CURRENT_TIMESTAMP()
            )
            """,
            [
                bigquery.ScalarQueryParameter("run_id", "STRING", run_id),
                bigquery.ScalarQueryParameter("mode", "STRING", mode),
                bigquery.ScalarQueryParameter("entity", "STRING", entity),
                bigquery.ScalarQueryParameter("start_date", "DATE", start_date),
                bigquery.ScalarQueryParameter("end_date", "DATE", end_date),
            ],
        )

    def finish_run(
        self,
        *,
        run_id: str,
        status: str,
        page_count: int,
        record_count: int,
        error: str | None = None,
    ) -> None:
        self._query(
            f"""
            UPDATE `{self._dataset}.ingestion_runs`
               SET status = @status,
                   page_count = @page_count,
                   record_count = @record_count,
                   finished_at = CURRENT_TIMESTAMP(),
                   error_message = @error
             WHERE run_id = @run_id
            """,
            [
                bigquery.ScalarQueryParameter("status", "STRING", status),
                bigquery.ScalarQueryParameter("page_count", "INT64", page_count),
                bigquery.ScalarQueryParameter("record_count", "INT64", record_count),
                bigquery.ScalarQueryParameter("error", "STRING", error),
                bigquery.ScalarQueryParameter("run_id", "STRING", run_id),
            ],
        )

    def is_day_complete(
        self,
        *,
        entity: str,
        day: date,
        modality: int | None,
    ) -> bool:
        rows = self._query(
            f"""
            SELECT 1
              FROM `{self._dataset}.ingestion_checkpoints`
             WHERE entity = @entity
               AND extraction_date = @day
               AND modality = @modality
             LIMIT 1
            """,
            [
                bigquery.ScalarQueryParameter("entity", "STRING", entity),
                bigquery.ScalarQueryParameter("day", "DATE", day),
                bigquery.ScalarQueryParameter("modality", "INT64", _modality_key(modality)),
            ],
        )
        return len(rows) > 0

    def mark_day_complete(
        self,
        *,
        entity: str,
        day: date,
        modality: int | None,
        last_page: int,
    ) -> None:
        self._query(
            f"""
            MERGE `{self._dataset}.ingestion_checkpoints` AS T
            USING (
                SELECT @entity AS entity,
                       @day AS extraction_date,
                       @modality AS modality,
                       @last_page AS last_page,
                       CURRENT_TIMESTAMP() AS updated_at
            ) AS S
            ON T.entity = S.entity
               AND T.extraction_date = S.extraction_date
               AND T.modality = S.modality
            WHEN MATCHED THEN
                UPDATE SET last_page = S.last_page, updated_at = S.updated_at
            WHEN NOT MATCHED THEN
                INSERT (entity, extraction_date, modality, last_page, updated_at)
                VALUES (S.entity, S.extraction_date, S.modality, S.last_page, S.updated_at)
            """,
            [
                bigquery.ScalarQueryParameter("entity", "STRING", entity),
                bigquery.ScalarQueryParameter("day", "DATE", day),
                bigquery.ScalarQueryParameter("modality", "INT64", _modality_key(modality)),
                bigquery.ScalarQueryParameter("last_page", "INT64", last_page),
            ],
        )

    def has_successful_snapshot(self, *, day: date) -> bool:
        rows = self._query(
            f"""
            SELECT 1 FROM `{self._dataset}.ingestion_runs`
             WHERE mode = 'snapshot'
               AND status = 'success'
               AND start_date = @day
               AND end_date = @day
             LIMIT 1
            """,
            [bigquery.ScalarQueryParameter("day", "DATE", day)],
        )
        return len(rows) > 0

    def get_watermark(self, *, entity: str) -> date | None:
        rows = self._query(
            f"""
            SELECT last_successful_date
              FROM `{self._dataset}.watermarks`
             WHERE entity = @entity
             LIMIT 1
            """,
            [bigquery.ScalarQueryParameter("entity", "STRING", entity)],
        )
        if not rows:
            return None
        value = rows[0][0]
        return value if isinstance(value, date) else date.fromisoformat(str(value))

    def set_watermark(self, *, entity: str, day: date) -> None:
        self._query(
            f"""
            MERGE `{self._dataset}.watermarks` AS T
            USING (
                SELECT @entity AS entity,
                       @day AS last_successful_date,
                       CURRENT_TIMESTAMP() AS updated_at
            ) AS S
            ON T.entity = S.entity
            WHEN MATCHED THEN
                UPDATE SET last_successful_date = S.last_successful_date,
                           updated_at = S.updated_at
            WHEN NOT MATCHED THEN
                INSERT (entity, last_successful_date, updated_at)
                VALUES (S.entity, S.last_successful_date, S.updated_at)
            """,
            [
                bigquery.ScalarQueryParameter("entity", "STRING", entity),
                bigquery.ScalarQueryParameter("day", "DATE", day),
            ],
        )

    def close(self) -> None:
        """Close the BigQuery client."""
        self._client.close()  # type: ignore[no-untyped-call]

    def _query(
        self,
        sql: str,
        parameters: list[bigquery.ScalarQueryParameter],
    ) -> list[Any]:
        config = bigquery.QueryJobConfig(query_parameters=parameters)
        return list(self._client.query(sql, job_config=config, location=self._location).result())


def _modality_key(modality: int | None) -> int:
    return 0 if modality is None else modality
