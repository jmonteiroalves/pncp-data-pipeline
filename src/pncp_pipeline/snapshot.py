"""Monthly snapshot date helpers."""

from __future__ import annotations

from datetime import date, timedelta


def first_tuesday(day: date) -> date:
    """Return the first Tuesday of the month containing ``day``."""
    first = day.replace(day=1)
    return first + timedelta(days=(1 - first.weekday()) % 7)


def snapshot_day_for(day: date) -> date:
    """Return the snapshot date for the current month.

    The snapshot is the first Tuesday. If a scheduled run is late, the caller
    can still use the same date, keeping month-to-month comparisons stable.
    """
    return first_tuesday(day)
