"""Tests for normalization, Gemini parsing, and enrichment orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from pncp_pipeline.config import Settings
from pncp_pipeline.enrichment.client import BatchResult, GeminiEnricher
from pncp_pipeline.enrichment.models import Candidate, EnrichmentInput, EnrichmentItem
from pncp_pipeline.enrichment.normalization import (
    description_hash,
    mask_pii,
    normalize_description,
)
from pncp_pipeline.enrichment.pipeline import EnrichmentPipeline


def test_normalization_strips_platform_prefix_and_whitespace() -> None:
    text = "[Portal de Compras Públicas] -   Aquisição   de notebooks  "

    assert normalize_description(text) == "Aquisição de notebooks"


def test_pii_is_masked() -> None:
    masked = mask_pii("Contato 123.456.789-00 ou email compras@example.com ou (11) 98765-4321")

    assert "123.456.789-00" not in masked
    assert "compras@example.com" not in masked
    assert "98765-4321" not in masked
    assert "[CPF]" in masked
    assert "[EMAIL]" in masked
    assert "[TELEFONE]" in masked


def test_hash_is_stable_and_case_insensitive() -> None:
    assert description_hash("Notebooks") == description_hash("notebooks")


class _FakeResponse:
    def __init__(self, text: str, *, input_tokens: int = 100, output_tokens: int = 40) -> None:
        self.text = text
        self.response_id = "req-1"
        self.usage_metadata = SimpleNamespace(
            prompt_token_count=input_tokens,
            candidates_token_count=output_tokens,
        )


class _FakeModels:
    def __init__(self, responses: list[Any]) -> None:
        self._responses = iter(responses)
        self.calls: list[str] = []

    def generate_content(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs["contents"])
        response = next(self._responses)
        if isinstance(response, Exception):
            raise response
        return response


class _FakeClient:
    def __init__(self, responses: list[Any]) -> None:
        self.models = _FakeModels(responses)


def _valid_json(item_id: str = "abc123") -> str:
    return (
        '{"items":[{"id":"' + item_id + '","categoria":"Tecnologia","subcategoria":"Hardware",'
        '"tipo_objeto":"bem","confianca":0.95,"justificativa":"Notebooks"}]}'
    )


def _enricher(responses: list[Any]) -> GeminiEnricher:
    return GeminiEnricher(
        project="test",
        location="global",
        model_id="gemini-3.5-flash-lite",
        client=_FakeClient(responses),
    )


def test_client_parses_valid_response() -> None:
    result = _enricher([_FakeResponse(_valid_json())]).classify(
        [EnrichmentInput(id="abc123", description="Notebooks")]
    )

    assert result.status == "success"
    assert result.items[0].categoria.value == "Tecnologia"
    assert result.input_tokens == 100
    assert result.output_tokens == 40


def test_client_repairs_invalid_response() -> None:
    result = _enricher([_FakeResponse("not json"), _FakeResponse(_valid_json())]).classify(
        [EnrichmentInput(id="abc123", description="Notebooks")]
    )

    assert result.status == "success"
    assert len(result.items) == 1


def test_client_fails_after_two_invalid_responses() -> None:
    result = _enricher([_FakeResponse("not json"), _FakeResponse("still not json")]).classify(
        [EnrichmentInput(id="abc123", description="Notebooks")]
    )

    assert result.status == "failed"
    assert result.items == []
    assert result.error


def test_client_fails_on_id_mismatch() -> None:
    result = _enricher(
        [_FakeResponse(_valid_json("other")), _FakeResponse(_valid_json("other"))]
    ).classify([EnrichmentInput(id="abc123", description="Notebooks")])

    assert result.status == "failed"
    assert "ids" in (result.error or "")


def test_client_reports_api_error() -> None:
    result = _enricher([RuntimeError("quota")]).classify(
        [EnrichmentInput(id="abc123", description="Notebooks")]
    )

    assert result.status == "error"
    assert "quota" in (result.error or "")


@dataclass
class _FakeStore:
    candidates: list[Candidate]
    cached: set[str]
    monthly_used: int = 0
    saved: tuple[list[Any], list[Any]] | None = None

    def fetch_candidates(self, limit: int) -> list[Candidate]:
        return self.candidates[:limit]

    def fetch_cached_hashes(self, prompt_version: str, model_id: str) -> set[str]:
        return set(self.cached)

    def monthly_item_count(self, prompt_version: str, model_id: str) -> int:
        return self.monthly_used

    def save(self, enrichments: list[Any], requests: list[Any]) -> None:
        self.saved = (list(enrichments), list(requests))


class _FakeEnricher:
    def __init__(self, status: str = "success") -> None:
        self.status = status
        self.batches: list[list[EnrichmentInput]] = []

    def classify(self, items: list[EnrichmentInput]) -> BatchResult:
        self.batches.append(list(items))
        if self.status != "success":
            return BatchResult(
                items=[],
                status=self.status,
                error="bad response",
                request_id="req",
                input_tokens=10,
                output_tokens=5,
                latency_ms=7,
            )
        return BatchResult(
            items=[
                EnrichmentItem(
                    id=item.id,
                    categoria="Tecnologia",
                    subcategoria="Hardware",
                    tipo_objeto="bem",
                    confianca=0.9,
                    justificativa="teste",
                )
                for item in items
            ],
            status="success",
            error=None,
            request_id="req",
            input_tokens=10,
            output_tokens=5,
            latency_ms=7,
        )


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "llm_monthly_cap": 100,
        "llm_sample_rate": 1.0,
        "llm_batch_size": 2,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_pipeline_samples_batches_and_saves() -> None:
    candidates = [
        Candidate(description=f"item {index}", description_hash=f"{index:064x}")
        for index in range(3)
    ]
    store = _FakeStore(candidates=candidates, cached=set())
    enricher = _FakeEnricher()
    pipeline = EnrichmentPipeline(store=store, enricher=enricher, settings=_settings())

    result = pipeline.run(limit=3)

    assert result.selected_count == 3
    assert result.batch_count == 2
    assert result.succeeded == 3
    assert result.failed == 0
    assert store.saved is not None
    assert len(store.saved[0]) == 3
    assert len(store.saved[1]) == 2
    assert all(record.validation_status == "valid" for record in store.saved[0])


def test_pipeline_skips_cached_and_respects_monthly_cap() -> None:
    candidates = [
        Candidate(description=f"item {index}", description_hash=f"{index:064x}")
        for index in range(4)
    ]
    store = _FakeStore(
        candidates=candidates,
        cached={candidates[0].description_hash},
        monthly_used=3,
    )
    pipeline = EnrichmentPipeline(
        store=store,
        enricher=_FakeEnricher(),
        settings=_settings(llm_monthly_cap=4),
    )

    result = pipeline.run(limit=10)

    assert result.cached_count == 1
    assert result.selected_count == 1
    assert result.monthly_remaining == 1


def test_pipeline_dry_run_does_not_save_or_call_api() -> None:
    candidates = [Candidate(description="item", description_hash="a" * 64)]
    store = _FakeStore(candidates=candidates, cached=set())
    enricher = _FakeEnricher()
    pipeline = EnrichmentPipeline(store=store, enricher=enricher, settings=_settings())

    result = pipeline.run(limit=1, dry_run=True)

    assert result.dry_run is True
    assert result.input_tokens > 0
    assert store.saved is None
    assert enricher.batches == []


def test_pipeline_stores_failed_rows_as_outros() -> None:
    candidates = [Candidate(description="item", description_hash="a" * 64)]
    store = _FakeStore(candidates=candidates, cached=set())
    pipeline = EnrichmentPipeline(
        store=store,
        enricher=_FakeEnricher(status="failed"),
        settings=_settings(),
    )

    result = pipeline.run(limit=1)

    assert result.failed == 1
    assert store.saved is not None
    assert store.saved[0][0].categoria == "Outros"
    assert store.saved[0][0].validation_status == "failed"
