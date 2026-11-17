"""SQL builders shared by the BigQuery backend and tests."""

from __future__ import annotations

BRONZE_COLUMNS: tuple[str, ...] = (
    "ingestion_id",
    "source",
    "entity",
    "endpoint",
    "request_params",
    "page",
    "record_index",
    "page_key",
    "gcs_uri",
    "record_id",
    "record_hash",
    "source_date",
    "api_status",
    "payload",
    "ingested_at",
)


def bronze_table_ddl(table: str) -> str:
    """Return the DDL for a Bronze table partitioned by business date."""
    return f"""
CREATE TABLE IF NOT EXISTS `{table}` (
    ingestion_id STRING,
    source STRING,
    entity STRING,
    endpoint STRING,
    request_params JSON,
    page INT64,
    record_index INT64,
    page_key STRING,
    gcs_uri STRING,
    record_id STRING,
    record_hash STRING,
    source_date DATE,
    api_status INT64,
    payload JSON,
    ingested_at TIMESTAMP
)
PARTITION BY source_date
CLUSTER BY entity, endpoint
"""


def bronze_merge_sql(target: str, staging: str) -> str:
    """Return the idempotent MERGE from staging into the Bronze table."""
    columns = ", ".join(BRONZE_COLUMNS)
    values = ", ".join(f"S.{column}" for column in BRONZE_COLUMNS)
    return f"""
MERGE `{target}` AS T
USING `{staging}` AS S
ON T.source_date = S.source_date AND T.record_id = S.record_id
WHEN NOT MATCHED THEN
  INSERT ({columns})
  VALUES ({values})
"""


def control_ddl(dataset: str) -> str:
    """Return the DDL for the control tables."""
    return f"""
CREATE TABLE IF NOT EXISTS `{dataset}.ingestion_runs` (
    run_id STRING,
    mode STRING,
    entity STRING,
    start_date DATE,
    end_date DATE,
    status STRING,
    page_count INT64,
    record_count INT64,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    error_message STRING
);

CREATE TABLE IF NOT EXISTS `{dataset}.ingestion_checkpoints` (
    entity STRING,
    extraction_date DATE,
    modality INT64,
    last_page INT64,
    updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS `{dataset}.watermarks` (
    entity STRING,
    last_successful_date DATE,
    updated_at TIMESTAMP
);
"""
