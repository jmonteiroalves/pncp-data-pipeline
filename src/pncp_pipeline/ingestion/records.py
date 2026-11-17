"""Row construction for the Bronze layer."""

from __future__ import annotations

from datetime import date
from typing import Any

from pncp_pipeline.hashing import canonical_json, sha256_text
from pncp_pipeline.pncp.models import Page

_DATE_FIELDS = ("dataPublicacaoPncp", "dataPublicacao", "dataAssinatura", "dataInclusao")


def source_date_of(payload: dict[str, Any], fallback: date) -> date:
    """Return the business date used to partition a Bronze record.

    Publication date is stable across re-ingestion, so it is a better
    partition key than the ingestion date. If the source omits it, the
    extraction date is used.
    """
    for field in _DATE_FIELDS:
        raw = payload.get(field)
        if isinstance(raw, str) and len(raw) >= 10:
            try:
                return date.fromisoformat(raw[:10])
            except ValueError:
                continue
    return fallback


def build_rows(page: Page) -> list[dict[str, Any]]:
    """Build one Bronze row per record in a page."""
    rows: list[dict[str, Any]] = []
    ingested_at = page.ingested_at.isoformat()
    gcs_uri = page.gcs_uri or ""

    for index, payload in enumerate(page.records):
        record_hash = sha256_text(canonical_json(payload))
        rows.append(
            {
                "ingestion_id": page.run_id,
                "source": "pncp",
                "entity": page.entity,
                "endpoint": page.endpoint,
                "request_params": dict(page.request_params),
                "page": page.page_number,
                "record_index": index,
                "page_key": page.page_key,
                "gcs_uri": gcs_uri,
                "record_id": sha256_text(f"{page.entity}|{record_hash}"),
                "record_hash": record_hash,
                "source_date": source_date_of(payload, page.extraction_date).isoformat(),
                "api_status": page.status_code,
                "payload": payload,
                "ingested_at": ingested_at,
            }
        )
    return rows
