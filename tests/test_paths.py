"""Tests for deterministic Bronze object paths."""

from __future__ import annotations

from datetime import UTC, date, datetime

from pncp_pipeline.pncp.models import Page
from pncp_pipeline.storage.paths import bronze_object_name


def _page(*, entity: str, modality: int | None) -> Page:
    return Page(
        entity=entity,  # type: ignore[arg-type]
        endpoint="/v1/contratacoes/publicacao",
        mode="publicacao",
        request_params={},
        extraction_date=date(2026, 1, 15),
        modality=modality,
        page_number=1,
        total_records=1,
        total_pages=1,
        status_code=200,
        records=[],
        page_key="13f9a89111c1" + "0" * 52,
        ingested_at=datetime(2026, 1, 15, tzinfo=UTC),
    )


def test_notice_path_includes_modality() -> None:
    name = bronze_object_name("bronze/pncp", _page(entity="contratacoes", modality=6))

    assert name == (
        "bronze/pncp/contratacoes/dt=2026-01-15/modality=6/page=0001-13f9a89111c1.jsonl.gz"
    )


def test_contract_path_omits_modality() -> None:
    name = bronze_object_name("bronze/pncp", _page(entity="contratos", modality=None))

    assert name == "bronze/pncp/contratos/dt=2026-01-15/page=0001-13f9a89111c1.jsonl.gz"
