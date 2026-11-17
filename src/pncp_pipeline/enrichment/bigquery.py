"""BigQuery persistence for enrichment candidates, cache, and results."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from google.cloud import bigquery

from pncp_pipeline.enrichment.models import Candidate, EnrichmentRecord, RequestRecord
from pncp_pipeline.enrichment.normalization import description_hash, normalize_description
from pncp_pipeline.enrichment.sql import (
    ENRICHMENT_COLUMNS,
    REQUEST_COLUMNS,
    enrichment_ddl,
)

ENRICHMENT_SCHEMA: tuple[bigquery.SchemaField, ...] = (
    bigquery.SchemaField("enrichment_id", "STRING"),
    bigquery.SchemaField("description_hash", "STRING"),
    bigquery.SchemaField("description", "STRING"),
    bigquery.SchemaField("categoria", "STRING"),
    bigquery.SchemaField("subcategoria", "STRING"),
    bigquery.SchemaField("tipo_objeto", "STRING"),
    bigquery.SchemaField("confianca", "FLOAT64"),
    bigquery.SchemaField("justificativa", "STRING"),
    bigquery.SchemaField("model_id", "STRING"),
    bigquery.SchemaField("prompt_version", "STRING"),
    bigquery.SchemaField("prompt_hash", "STRING"),
    bigquery.SchemaField("taxonomy_version", "STRING"),
    bigquery.SchemaField("temperature", "FLOAT64"),
    bigquery.SchemaField("request_id", "STRING"),
    bigquery.SchemaField("latency_ms", "INT64"),
    bigquery.SchemaField("validation_status", "STRING"),
    bigquery.SchemaField("validation_errors", "STRING"),
    bigquery.SchemaField("created_at", "TIMESTAMP"),
)

REQUEST_SCHEMA: tuple[bigquery.SchemaField, ...] = (
    bigquery.SchemaField("request_id", "STRING"),
    bigquery.SchemaField("run_id", "STRING"),
    bigquery.SchemaField("model_id", "STRING"),
    bigquery.SchemaField("prompt_version", "STRING"),
    bigquery.SchemaField("taxonomy_version", "STRING"),
    bigquery.SchemaField("batch_index", "INT64"),
    bigquery.SchemaField("item_count", "INT64"),
    bigquery.SchemaField("input_tokens", "INT64"),
    bigquery.SchemaField("output_tokens", "INT64"),
    bigquery.SchemaField("total_tokens", "INT64"),
    bigquery.SchemaField("cost_usd", "FLOAT64"),
    bigquery.SchemaField("latency_ms", "INT64"),
    bigquery.SchemaField("status", "STRING"),
    bigquery.SchemaField("error_message", "STRING"),
    bigquery.SchemaField("created_at", "TIMESTAMP"),
)


class BigQueryEnrichmentStore:
    """Reads Silver descriptions and writes AI results to BigQuery."""

    def __init__(
        self,
        *,
        project: str,
        silver_dataset: str = "silver",
        ai_dataset: str = "ai",
        control_dataset: str = "control",
        location: str = "US",
    ) -> None:
        self._project = project
        self._silver = silver_dataset
        self._ai = ai_dataset
        self._control = control_dataset
        self._location = location
        self._client = bigquery.Client(project=project, location=location)
        self.ensure_tables()

    def ensure_tables(self) -> None:
        """Create the AI and request audit tables if needed."""
        self._client.query(
            enrichment_ddl(self._project, self._ai, self._control),
            location=self._location,
        ).result()

    def fetch_candidates(self, limit: int) -> list[Candidate]:
        """Return distinct normalised descriptions from Silver."""
        if limit <= 0:
            return []
        sql = f"""
            SELECT DISTINCT objeto_compra
              FROM `{self._project}.{self._silver}.contratacoes`
             WHERE objeto_compra IS NOT NULL
               AND TRIM(objeto_compra) != ''
             ORDER BY objeto_compra
             LIMIT @limit
        """
        config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("limit", "INT64", limit)]
        )
        rows = list(
            self._client.query(
                sql,
                job_config=config,
                location=self._location,
            ).result()
        )
        seen: set[str] = set()
        candidates: list[Candidate] = []
        for row in rows:
            description = normalize_description(str(row[0]))
            if not description:
                continue
            digest = description_hash(description)
            if digest in seen:
                continue
            seen.add(digest)
            candidates.append(Candidate(description=description, description_hash=digest))
        return candidates

    def fetch_cached_hashes(self, prompt_version: str, model_id: str) -> set[str]:
        """Return descriptions already classified for this prompt and model."""
        sql = f"""
            SELECT DISTINCT description_hash
              FROM `{self._project}.{self._ai}.classificacao`
             WHERE prompt_version = @prompt_version
               AND model_id = @model_id
               AND validation_status = 'valid'
        """
        config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("prompt_version", "STRING", prompt_version),
                bigquery.ScalarQueryParameter("model_id", "STRING", model_id),
            ]
        )
        rows = self._client.query(
            sql,
            job_config=config,
            location=self._location,
        ).result()
        return {str(row[0]) for row in rows}

    def fetch_predictions(self, prompt_version: str, model_id: str) -> dict[str, str]:
        """Return the latest valid category per description hash."""
        sql = f"""
            SELECT description_hash, categoria
              FROM `{self._project}.{self._ai}.classificacao`
             WHERE prompt_version = @prompt_version
               AND model_id = @model_id
               AND validation_status = 'valid'
             QUALIFY ROW_NUMBER() OVER (
                 PARTITION BY description_hash ORDER BY created_at DESC
             ) = 1
        """
        config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("prompt_version", "STRING", prompt_version),
                bigquery.ScalarQueryParameter("model_id", "STRING", model_id),
            ]
        )
        rows = self._client.query(
            sql,
            job_config=config,
            location=self._location,
        ).result()
        return {str(row[0]): str(row[1]) for row in rows}

    def monthly_item_count(self, prompt_version: str, model_id: str) -> int:
        """Return how many items were sent to this prompt and model this month."""
        sql = f"""
            SELECT COALESCE(SUM(item_count), 0) AS item_count
              FROM `{self._project}.{self._control}.llm_requests`
             WHERE prompt_version = @prompt_version
               AND model_id = @model_id
               AND created_at >= TIMESTAMP_TRUNC(CURRENT_TIMESTAMP(), MONTH)
        """
        config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("prompt_version", "STRING", prompt_version),
                bigquery.ScalarQueryParameter("model_id", "STRING", model_id),
            ]
        )
        rows = list(
            self._client.query(
                sql,
                job_config=config,
                location=self._location,
            ).result()
        )
        return int(rows[0][0]) if rows else 0

    def save(
        self,
        enrichments: Sequence[EnrichmentRecord],
        requests: Sequence[RequestRecord],
    ) -> None:
        """Append AI results and request logs."""
        if enrichments:
            self._load(
                table=f"{self._project}.{self._ai}.classificacao",
                rows=[asdict(record) for record in enrichments],
                schema=ENRICHMENT_SCHEMA,
            )
        if requests:
            self._load(
                table=f"{self._project}.{self._control}.llm_requests",
                rows=[asdict(record) for record in requests],
                schema=REQUEST_SCHEMA,
            )

    def close(self) -> None:
        """Close the BigQuery client."""
        self._client.close()  # type: ignore[no-untyped-call]

    def _load(
        self,
        *,
        table: str,
        rows: list[dict[str, Any]],
        schema: tuple[bigquery.SchemaField, ...],
    ) -> None:
        job_config = bigquery.LoadJobConfig(
            schema=list(schema),
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        )
        job = self._client.load_table_from_json(
            rows,
            table,
            job_config=job_config,
            location=self._location,
        )
        job.result()


def now_iso() -> str:
    """Return the current UTC timestamp in ISO-8601 format."""
    return datetime.now(tz=UTC).isoformat()


__all__ = [
    "BigQueryEnrichmentStore",
    "ENRICHMENT_COLUMNS",
    "ENRICHMENT_SCHEMA",
    "REQUEST_COLUMNS",
    "REQUEST_SCHEMA",
    "now_iso",
]
