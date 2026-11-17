"""Tests for Bronze row construction."""

from __future__ import annotations

from datetime import UTC, date, datetime

from pncp_pipeline.ingestion.records import build_rows, source_date_of
from pncp_pipeline.pncp.models import Page


def _page(records: list[dict[str, object]], *, run_id: str = "run-1") -> Page:
    return Page(
        entity="contratacoes",
        endpoint="/v1/contratacoes/publicacao",
        mode="publicacao",
        request_params={"pagina": 1, "dataInicial": "20260115"},
        extraction_date=date(2026, 1, 15),
        modality=6,
        page_number=1,
        total_records=len(records),
        total_pages=1,
        status_code=200,
        records=records,
        page_key="page-key",
        ingested_at=datetime(2026, 1, 15, 12, 0, tzinfo=UTC),
        run_id=run_id,
        gcs_uri="gs://bucket/object.jsonl.gz",
    )


def test_source_date_prefers_publication_date() -> None:
    payload = {"dataPublicacaoPncp": "2026-01-10T08:00:00"}

    assert source_date_of(payload, date(2026, 2, 1)) == date(2026, 1, 10)


def test_source_date_falls_back_to_extraction_date() -> None:
    assert source_date_of({}, date(2026, 2, 1)) == date(2026, 2, 1)


def test_build_rows_is_deterministic_and_traceable() -> None:
    records = [{"numeroControlePNCP": "abc", "objetoCompra": "computadores"}]

    first = build_rows(_page(records))
    second = build_rows(_page(records, run_id="run-2"))

    assert len(first) == 1
    assert first[0]["record_id"] == second[0]["record_id"]
    assert first[0]["record_hash"] == second[0]["record_hash"]
    assert first[0]["source_date"] == "2026-01-15"
    assert first[0]["gcs_uri"] == "gs://bucket/object.jsonl.gz"
    assert first[0]["request_params"] == {"pagina": 1, "dataInicial": "20260115"}
    assert first[0]["payload"] == records[0]


def test_record_id_changes_when_payload_changes() -> None:
    first = build_rows(_page([{"id": 1, "value": "a"}]))[0]
    second = build_rows(_page([{"id": 1, "value": "b"}]))[0]

    assert first["record_id"] != second["record_id"]
