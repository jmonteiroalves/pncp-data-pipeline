"""CLI tests."""

import json

import pytest

from pncp_pipeline import __version__
from pncp_pipeline.cli import build_parser, main


def test_config_command_prints_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["config"]) == 0

    payload = json.loads(capsys.readouterr().out)

    assert payload["environment"] == "dev"
    assert payload["pncp_page_size"] == 50


def test_version_command(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["version"]) == 0

    assert capsys.readouterr().out.strip() == __version__


def test_missing_command_returns_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 2

    assert "usage" in capsys.readouterr().err.lower()


def test_backfill_parser_accepts_iso_dates() -> None:
    args = build_parser().parse_args(
        [
            "backfill",
            "--start",
            "2026-01-15",
            "--end",
            "2026-01-16",
            "--entity",
            "contratacoes",
            "--modality",
            "6",
            "--local",
        ]
    )

    assert args.start.isoformat() == "2026-01-15"
    assert args.end.isoformat() == "2026-01-16"
    assert args.modalities == [6]
    assert args.local is True


def test_invalid_date_is_rejected() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["backfill", "--start", "15/01/2026", "--end", "2026-01-16"])
