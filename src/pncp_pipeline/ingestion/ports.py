"""Ingestion ports used by the pipeline orchestration."""

from __future__ import annotations

from datetime import date
from typing import Protocol

from pncp_pipeline.pncp.models import Page


class BronzeStore(Protocol):
    """Writes raw pages to the data lake."""

    def write_page(self, page: Page) -> str:
        """Persist a page and return its URI."""
        ...


class BronzeLoader(Protocol):
    """Loads raw pages into the warehouse."""

    def load_page(self, page: Page) -> int:
        """Load a page and return the number of new rows."""
        ...


class ControlStore(Protocol):
    """Stores run history, checkpoints, and watermarks."""

    def start_run(
        self,
        *,
        run_id: str,
        mode: str,
        entity: str,
        start_date: date,
        end_date: date,
    ) -> None: ...

    def finish_run(
        self,
        *,
        run_id: str,
        status: str,
        page_count: int,
        record_count: int,
        error: str | None = None,
    ) -> None: ...

    def is_day_complete(
        self,
        *,
        entity: str,
        day: date,
        modality: int | None,
    ) -> bool: ...

    def mark_day_complete(
        self,
        *,
        entity: str,
        day: date,
        modality: int | None,
        last_page: int,
    ) -> None: ...

    def has_successful_snapshot(self, *, day: date) -> bool: ...

    def get_watermark(self, *, entity: str) -> date | None: ...

    def set_watermark(self, *, entity: str, day: date) -> None: ...
