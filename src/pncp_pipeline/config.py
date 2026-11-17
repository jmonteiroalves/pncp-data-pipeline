"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, HttpUrl, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Validated runtime configuration.

    Values are read from environment variables and, when present, from a local
    ``.env`` file. Variable names are case-insensitive, so ``GCP_PROJECT`` maps
    to ``gcp_project``.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        validate_default=True,
    )

    environment: Literal["dev", "test", "prod"] = "dev"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    gcp_project: str = Field(default="local-project", min_length=1)
    bq_location: str = Field(default="US", pattern=r"^[A-Za-z0-9-]+$")
    gcs_bucket: str = Field(
        default="local-bucket",
        min_length=3,
        max_length=63,
        pattern=r"^[a-z0-9][a-z0-9._-]*[a-z0-9]$",
    )
    gcs_prefix: str = Field(default="bronze/pncp", min_length=1)
    bronze_dataset: str = Field(default="bronze", pattern=r"^[A-Za-z0-9_]+$")
    silver_dataset: str = Field(default="silver", pattern=r"^[A-Za-z0-9_]+$")
    ai_dataset: str = Field(default="ai", pattern=r"^[A-Za-z0-9_]+$")
    control_dataset: str = Field(default="control", pattern=r"^[A-Za-z0-9_]+$")
    local_data_dir: Path = Path("data")

    pncp_base_url: HttpUrl = HttpUrl("https://pncp.gov.br/api/consulta")
    pncp_request_interval_seconds: float = Field(default=1.25, ge=0.5, le=60.0)
    pncp_max_retries: int = Field(default=5, ge=1, le=10)
    pncp_page_size: int = Field(default=50, ge=10, le=50)
    pncp_contract_page_size: int = Field(default=500, ge=10, le=500)
    pncp_timeout_seconds: float = Field(default=60.0, ge=1.0, le=300.0)
    pncp_modalities: Annotated[list[int], NoDecode] = [
        1,
        4,
        5,
        6,
        7,
        8,
        9,
        10,
        11,
        12,
    ]

    vertex_location: str = Field(default="global", min_length=1)
    llm_model: str = Field(default="gemini-3.1-flash-lite", min_length=1)
    llm_temperature: float = Field(default=0.0, ge=0.0, le=1.0)
    llm_sample_rate: float = Field(default=0.1, ge=0.0, le=1.0)
    llm_input_price_per_million: float = Field(default=0.25, ge=0.0)
    llm_output_price_per_million: float = Field(default=1.50, ge=0.0)
    llm_prompt_version: str = Field(default="v1", min_length=1)
    llm_taxonomy_version: str = Field(default="v1", min_length=1)
    llm_batch_size: int = Field(default=20, ge=1, le=50)
    llm_monthly_cap: int = Field(default=10_000, ge=0)
    llm_monthly_budget_usd: float = Field(default=10.0, ge=0.0)

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalise_log_level(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("pncp_modalities", mode="before")
    @classmethod
    def _parse_modalities(cls, value: object) -> object:
        if isinstance(value, str):
            return [int(part) for part in value.replace(" ", "").split(",") if part]
        return value

    @field_validator("pncp_modalities")
    @classmethod
    def _validate_modalities(cls, value: list[int]) -> list[int]:
        if not value:
            raise ValueError("at least one modality code is required")
        if len(set(value)) != len(value):
            raise ValueError("modality codes must be unique")
        if any(code < 1 or code > 99 for code in value):
            raise ValueError("modality codes must be between 1 and 99")
        return value

    @property
    def is_production(self) -> bool:
        """Return True when the pipeline runs against the production project."""
        return self.environment == "prod"

    def safe_summary(self) -> dict[str, object]:
        """Return a JSON-serialisable view of the configuration.

        The pipeline holds no secrets: cloud access uses Application Default
        Credentials and IAM. This method exists to make that explicit and to
        provide a stable output for the ``config`` CLI command.
        """
        return self.model_dump(mode="json")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()
