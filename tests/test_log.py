"""Structured logging tests."""

import json

import pytest

from pncp_pipeline.log import (
    configure_logging,
    get_logger,
    reset_run_context,
    set_run_context,
)


def test_json_log_includes_run_context(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    set_run_context("run-123", "ingest")

    get_logger("pncp_pipeline.test").info("started", extra={"rows": 3})
    reset_run_context()

    payload = json.loads(capsys.readouterr().err.strip().splitlines()[-1])

    assert payload["severity"] == "INFO"
    assert payload["message"] == "started"
    assert payload["run_id"] == "run-123"
    assert payload["job"] == "ingest"
    assert payload["rows"] == 3


def test_context_is_cleared(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    get_logger("pncp_pipeline.test").info("done")

    payload = json.loads(capsys.readouterr().err.strip().splitlines()[-1])

    assert "run_id" not in payload
    assert "job" not in payload


def test_exception_is_serialised(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    logger = get_logger("pncp_pipeline.test")

    try:
        raise ValueError("boom")
    except ValueError:
        logger.exception("failed")

    payload = json.loads(capsys.readouterr().err.strip().splitlines()[-1])

    assert payload["severity"] == "ERROR"
    assert "ValueError: boom" in payload["exception"]
