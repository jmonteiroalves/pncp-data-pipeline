"""Tests for generated SQL."""

from pncp_pipeline.warehouse.bigquery import BRONZE_SCHEMA
from pncp_pipeline.warehouse.sql import (
    BRONZE_COLUMNS,
    bronze_merge_sql,
    bronze_table_ddl,
    control_ddl,
)


def test_schema_matches_insert_column_order() -> None:
    assert tuple(field.name for field in BRONZE_SCHEMA) == BRONZE_COLUMNS


def test_bronze_ddl_is_partitioned_and_clustered() -> None:
    ddl = bronze_table_ddl("project.bronze.pncp_contratacoes_raw")

    assert "PARTITION BY source_date" in ddl
    assert "CLUSTER BY entity, endpoint" in ddl
    assert "`project.bronze.pncp_contratacoes_raw`" in ddl


def test_merge_is_idempotent_by_record() -> None:
    sql = bronze_merge_sql("project.bronze.target", "project.bronze.staging")

    assert "T.source_date = S.source_date" in sql
    assert "T.record_id = S.record_id" in sql
    assert "WHEN NOT MATCHED THEN" in sql
    assert "S.payload" in sql


def test_control_ddl_creates_expected_tables() -> None:
    ddl = control_ddl("project.control")

    assert "`project.control.ingestion_runs`" in ddl
    assert "`project.control.ingestion_checkpoints`" in ddl
    assert "`project.control.watermarks`" in ddl
