"""Ingestion result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass(slots=True)
class RunResult:
    """Summary of an ingestion run."""

    run_id: str
    mode: str
    entities: list[str]
    start_date: date
    end_date: date
    page_count: int
    record_count: int
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation."""
        return {
            "run_id": self.run_id,
            "mode": self.mode,
            "entities": self.entities,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "page_count": self.page_count,
            "record_count": self.record_count,
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "error": self.error,
            "details": self.details,
        }
