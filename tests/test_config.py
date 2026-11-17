"""Configuration tests."""

import json

import pytest
from pydantic import ValidationError

from pncp_pipeline.config import Settings


def test_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.environment == "dev"
    assert settings.log_level == "INFO"
    assert settings.pncp_request_interval_seconds == 1.25
    assert settings.pncp_page_size == 50
    assert settings.pncp_contract_page_size == 500
    assert settings.pncp_modalities == [1, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    assert settings.llm_batch_size == 20
    assert settings.llm_monthly_cap == 10_000
    assert str(settings.pncp_base_url) == "https://pncp.gov.br/api/consulta"


def test_modalities_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PNCP_MODALITIES", "1, 6,8")

    settings = Settings(_env_file=None)

    assert settings.pncp_modalities == [1, 6, 8]


@pytest.mark.parametrize("value", ["0", "100", "6,6"])
def test_modalities_must_be_valid(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("PNCP_MODALITIES", value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_environment_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GCP_PROJECT", "test-project")
    monkeypatch.setenv("PNCP_PAGE_SIZE", "25")
    monkeypatch.setenv("LOG_LEVEL", "debug")
    monkeypatch.setenv("LLM_MONTHLY_CAP", "500")

    settings = Settings(_env_file=None)

    assert settings.gcp_project == "test-project"
    assert settings.pncp_page_size == 25
    assert settings.log_level == "DEBUG"
    assert settings.llm_monthly_cap == 500


def test_safe_summary_is_json_serialisable() -> None:
    settings = Settings(_env_file=None)

    summary = settings.safe_summary()

    assert summary["pncp_base_url"] == "https://pncp.gov.br/api/consulta"
    assert json.loads(json.dumps(summary))["gcp_project"] == "local-project"


@pytest.mark.parametrize("value", ["5", "51"])
def test_page_size_must_respect_api_bounds(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("PNCP_PAGE_SIZE", value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_interval_must_respect_rate_limit_floor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PNCP_REQUEST_INTERVAL_SECONDS", "0.1")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_bucket_name_must_be_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GCS_BUCKET", "Invalid_Bucket")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_is_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "prod")

    assert Settings(_env_file=None).is_production is True
