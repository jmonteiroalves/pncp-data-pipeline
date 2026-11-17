"""End-to-end ingestion tests against a mock PNCP API and local storage."""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from pncp_pipeline.ingestion.pipeline import IngestionPipeline
from pncp_pipeline.pncp.client import PNCPClient, PNCPError
from pncp_pipeline.storage.local import LocalBronzeStore
from pncp_pipeline.warehouse.sqlite import SQLiteBronzeLoader, SQLiteControlStore


def _notice(page: int, index: int) -> dict[str, Any]:
    return {
        "numeroControlePNCP": f"orgao-1-{page:06d}/{index}/2026",
        "objetoCompra": f"item {page}-{index}",
        "dataPublicacaoPncp": "2026-01-15T10:00:00",
        "valorTotalEstimado": 1000 + index,
    }


def _paged_handler(
    *,
    pages: int = 2,
    per_page: int = 2,
    entity: str = "contratacoes",
    path_fragment: str = "/v1/contratacoes/publicacao",
) -> Any:
    def handler(request: httpx.Request) -> httpx.Response:
        assert path_fragment in request.url.path
        page = int(request.url.params["pagina"])
        records = [_notice(page, index) for index in range(per_page)]
        return httpx.Response(
            200,
            json={
                "data": records,
                "totalRegistros": pages * per_page,
                "totalPaginas": pages,
                "numeroPagina": page,
                "paginasRestantes": max(pages - page, 0),
            },
        )

    return handler


def _build(
    tmp_path: Path,
    handler: Any,
    *,
    max_retries: int = 2,
) -> tuple[IngestionPipeline, Path, SQLiteControlStore, PNCPClient]:
    database = tmp_path / "local.db"
    store = LocalBronzeStore(tmp_path, "bronze/pncp")
    loader = SQLiteBronzeLoader(database)
    control = SQLiteControlStore(database)
    client = PNCPClient(
        "https://pncp.gov.br/api/consulta",
        request_interval_seconds=0,
        max_retries=max_retries,
        page_size=50,
        contract_page_size=500,
        timeout_seconds=5,
        transport=httpx.MockTransport(handler),
        sleep=lambda _seconds: None,
    )
    pipeline = IngestionPipeline(client=client, store=store, loader=loader, control=control)
    return pipeline, database, control, client


def test_backfill_is_resumable_and_idempotent(tmp_path: Path) -> None:
    pipeline, database, control, client = _build(tmp_path, _paged_handler())
    day = date(2026, 1, 15)

    try:
        first = pipeline.backfill(
            start=day,
            end=day,
            entities=("contratacoes",),
            modalities=(6,),
            max_pages=1,
        )
        assert first.page_count == 1
        assert first.record_count == 2
        assert not control.is_day_complete(entity="contratacoes", day=day, modality=6)

        second = pipeline.backfill(
            start=day,
            end=day,
            entities=("contratacoes",),
            modalities=(6,),
        )
        assert second.page_count == 2
        # Page 1 is re-fetched but deduplicated; only page 2 is new.
        assert second.record_count == 2
        assert control.is_day_complete(entity="contratacoes", day=day, modality=6)

        third = pipeline.backfill(
            start=day,
            end=day,
            entities=("contratacoes",),
            modalities=(6,),
        )
        assert third.page_count == 0
        assert third.record_count == 0
        assert third.details["skipped_days"] == 1
    finally:
        client.close()

    connection = sqlite3.connect(database)
    try:
        total = connection.execute("SELECT COUNT(*) FROM bronze_records").fetchone()[0]
        statuses = [
            row[0]
            for row in connection.execute(
                "SELECT status FROM ingestion_runs ORDER BY started_at"
            ).fetchall()
        ]
    finally:
        connection.close()

    assert total == 4
    assert statuses == ["success", "success", "success"]
    assert len(list((tmp_path / "bronze").rglob("*.jsonl.gz"))) == 2


def test_failed_run_is_recorded(tmp_path: Path) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    pipeline, database, _control, client = _build(tmp_path, handler, max_retries=1)
    try:
        with pytest.raises(PNCPError):
            pipeline.backfill(
                start=date(2026, 1, 15),
                end=date(2026, 1, 15),
                entities=("contratacoes",),
                modalities=(6,),
            )
    finally:
        client.close()

    connection = sqlite3.connect(database)
    try:
        status, error = connection.execute(
            "SELECT status, error_message FROM ingestion_runs ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
    finally:
        connection.close()

    assert status == "failed"
    assert "500" in error


def test_delta_uses_update_endpoint_and_advances_watermark(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "data": [_notice(1, 0)],
                "totalRegistros": 1,
                "totalPaginas": 1,
                "numeroPagina": 1,
                "paginasRestantes": 0,
            },
        )

    pipeline, _database, control, client = _build(tmp_path, handler)
    try:
        result = pipeline.delta(
            entities=("contratacoes",),
            modalities=(6,),
            window_days=2,
        )
    finally:
        client.close()

    today = datetime.now(tz=UTC).date()
    assert result.record_count == 1
    assert control.get_watermark(entity="contratacoes") == today
    assert requests[0].url.path == "/api/consulta/v1/contratacoes/atualizacao"
    assert requests[0].url.params["dataInicial"] == (today - timedelta(days=2)).strftime("%Y%m%d")
