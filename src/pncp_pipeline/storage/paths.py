"""Deterministic Bronze object paths shared by local and cloud storage."""

from __future__ import annotations

from pncp_pipeline.pncp.models import Page


def bronze_object_name(prefix: str, page: Page) -> str:
    """Return the relative object name for a raw page."""
    parts = [prefix.strip("/"), page.entity, f"dt={page.extraction_date.isoformat()}"]
    if page.modality is not None:
        parts.append(f"modality={page.modality}")
    parts.append(f"page={page.page_number:04d}-{page.page_key[:12]}.jsonl.gz")
    return "/".join(parts)
