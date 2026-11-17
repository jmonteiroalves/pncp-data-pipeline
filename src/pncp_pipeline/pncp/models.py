"""PNCP API client and models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal

Entity = Literal["contratacoes", "contratos"]
Mode = Literal["publicacao", "atualizacao"]


@dataclass(slots=True)
class Page:
    """A single page returned by the PNCP API."""

    entity: Entity
    endpoint: str
    mode: Mode
    request_params: dict[str, Any]
    extraction_date: date
    modality: int | None
    page_number: int
    total_records: int
    total_pages: int
    status_code: int
    records: list[dict[str, Any]]
    page_key: str
    ingested_at: datetime
    run_id: str = ""
    gcs_uri: str | None = field(default=None)
