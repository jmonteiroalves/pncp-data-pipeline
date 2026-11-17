"""Tests for the cloud backends using mocked clients."""

from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import MagicMock, patch

from pncp_pipeline.pncp.models import Page
from pncp_pipeline.warehouse.bigquery import BigQueryBronzeLoader


def _page() -> Page:
    return Page(
        entity="contratacoes",
        endpoint="/v1/contratacoes/publicacao",
        mode="publicacao",
        request_params={"pagina": 1},
        extraction_date=date(2026, 1, 15),
        modality=6,
        page_number=1,
        total_records=1,
        total_pages=1,
        status_code=200,
        records=[{"numeroControlePNCP": "abc", "dataPublicacaoPncp": "2026-01-15"}],
        page_key="a" * 64,
        ingested_at=datetime(2026, 1, 15, tzinfo=UTC),
        run_id="run-1",
        gcs_uri="gs://bucket/page.jsonl.gz",
    )


@patch("pncp_pipeline.warehouse.bigquery.bigquery.Client")
def test_bigquery_loader_loads_then_merges(client_class: MagicMock) -> None:
    client = client_class.return_value
    loader = BigQueryBronzeLoader("project", "bronze", "US")

    count = loader.load_page(_page())

    assert count == 1
    client.load_table_from_json.assert_called_once()
    load_args = client.load_table_from_json.call_args
    assert load_args.args[1] == "project.bronze._staging_contratacoes"
    rows = load_args.args[0]
    assert rows[0]["record_id"]
    assert rows[0]["payload"]["numeroControlePNCP"] == "abc"

    merge_sql = client.query.call_args.args[0]
    assert "MERGE `project.bronze.pncp_contratacoes_raw`" in merge_sql
    assert "T.record_id = S.record_id" in merge_sql
    client.load_table_from_json.return_value.result.assert_called_once()
    client.query.return_value.result.assert_called_once()


@patch("pncp_pipeline.storage.gcs.storage.Client")
def test_gcs_store_uploads_with_generation_guard(client_class: MagicMock) -> None:
    from pncp_pipeline.storage.gcs import GCSBronzeStore

    bucket = client_class.return_value.bucket.return_value
    blob = bucket.blob.return_value
    store = GCSBronzeStore("project", "bucket", "bronze/pncp")

    uri = store.write_page(_page())

    assert uri == (
        "gs://bucket/bronze/pncp/contratacoes/dt=2026-01-15/modality=6/"
        f"page=0001-{'a' * 12}.jsonl.gz"
    )
    blob.upload_from_string.assert_called_once()
    kwargs = blob.upload_from_string.call_args.kwargs
    assert kwargs["if_generation_match"] == 0
    assert kwargs["content_type"] == "application/gzip"
