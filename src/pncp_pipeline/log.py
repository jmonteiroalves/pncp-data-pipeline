"""Structured JSON logging for Cloud Run and local runs."""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any, TextIO

_RUN_ID: ContextVar[str | None] = ContextVar("run_id", default=None)
_JOB: ContextVar[str | None] = ContextVar("job", default=None)

_RESERVED_KEYS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
        "taskName",
    }
)


class JsonFormatter(logging.Formatter):
    """Render log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "severity": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        run_id = _RUN_ID.get()
        job = _JOB.get()
        if run_id is not None:
            payload["run_id"] = run_id
        if job is not None:
            payload["job"] = job

        for key, value in record.__dict__.items():
            if key not in _RESERVED_KEYS and not key.startswith("_"):
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO", stream: TextIO | None = None) -> None:
    """Configure the root logger to emit JSON to stderr.

    stderr is used so that CLI output written to stdout stays machine-readable.
    Cloud Run captures both streams and parses the JSON severity field.
    """
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(JsonFormatter())

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        handlers=[handler],
        force=True,
    )
    # The HTTP client logs every request at INFO; keep our logs signal-rich.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("google_genai").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a logger by name."""
    return logging.getLogger(name)


def set_run_context(run_id: str, job: str | None = None) -> None:
    """Attach run metadata to every log record emitted in this context."""
    _RUN_ID.set(run_id)
    _JOB.set(job)


def reset_run_context() -> None:
    """Clear run metadata from the logging context."""
    _RUN_ID.set(None)
    _JOB.set(None)
