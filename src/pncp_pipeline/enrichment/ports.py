"""Ports for enrichment persistence."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from pncp_pipeline.enrichment.models import Candidate, EnrichmentRecord, RequestRecord


class EnrichmentStore(Protocol):
    """Reads candidates and caches, and persists enrichment results."""

    def fetch_candidates(self, limit: int) -> list[Candidate]: ...

    def fetch_cached_hashes(self, prompt_version: str, model_id: str) -> set[str]: ...

    def monthly_item_count(self, prompt_version: str, model_id: str) -> int: ...

    def save(
        self,
        enrichments: Sequence[EnrichmentRecord],
        requests: Sequence[RequestRecord],
    ) -> None: ...
