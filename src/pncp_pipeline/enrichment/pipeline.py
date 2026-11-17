"""Enrichment orchestration: sample, call Gemini, validate, cache, and audit."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pncp_pipeline.config import Settings
from pncp_pipeline.enrichment.client import BatchResult, GeminiEnricher
from pncp_pipeline.enrichment.models import (
    Candidate,
    EnrichmentInput,
    EnrichmentRecord,
    RequestRecord,
)
from pncp_pipeline.enrichment.ports import EnrichmentStore
from pncp_pipeline.enrichment.prompt import PROMPT_HASH, PROMPT_VERSION, SYSTEM_PROMPT
from pncp_pipeline.enrichment.taxonomy import TAXONOMY_VERSION
from pncp_pipeline.log import get_logger, reset_run_context, set_run_context

logger = get_logger(__name__)


@dataclass(slots=True)
class EnrichmentRunResult:
    """Summary of an enrichment run."""

    run_id: str
    dry_run: bool
    candidate_count: int
    cached_count: int
    pending_count: int
    sampled_count: int
    selected_count: int
    batch_count: int
    succeeded: int
    failed: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    monthly_used_before: int
    monthly_remaining: int
    started_at: datetime
    finished_at: datetime

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation."""
        return {
            "run_id": self.run_id,
            "dry_run": self.dry_run,
            "candidate_count": self.candidate_count,
            "cached_count": self.cached_count,
            "pending_count": self.pending_count,
            "sampled_count": self.sampled_count,
            "selected_count": self.selected_count,
            "batch_count": self.batch_count,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": round(self.cost_usd, 6),
            "monthly_used_before": self.monthly_used_before,
            "monthly_remaining": self.monthly_remaining,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
        }


class EnrichmentPipeline:
    """Coordinate a batch enrichment run against BigQuery and Gemini."""

    def __init__(
        self,
        *,
        store: EnrichmentStore,
        enricher: GeminiEnricher,
        settings: Settings,
    ) -> None:
        self._store = store
        self._enricher = enricher
        self._settings = settings

    def run(
        self,
        *,
        limit: int | None = None,
        dry_run: bool = False,
        batch_size: int | None = None,
        sample_rate: float | None = None,
        only_hashes: set[str] | None = None,
    ) -> EnrichmentRunResult:
        """Run one enrichment pass."""
        run_id = uuid4().hex
        started_at = datetime.now(tz=UTC)
        set_run_context(run_id, "enrich")

        model_id = self._settings.llm_model
        prompt_version = PROMPT_VERSION
        taxonomy_version = TAXONOMY_VERSION
        effective_batch_size = batch_size or self._settings.llm_batch_size
        effective_rate = sample_rate if sample_rate is not None else self._settings.llm_sample_rate

        try:
            monthly_used = self._store.monthly_item_count(prompt_version, model_id)
            monthly_remaining = max(
                0,
                self._settings.llm_monthly_cap - monthly_used,
            )

            fetch_limit = min(
                50_000,
                max(1_000, (limit or 5_000) * 10 if effective_rate < 1 else (limit or 5_000)),
            )
            candidates = self._store.fetch_candidates(fetch_limit)
            cached = self._store.fetch_cached_hashes(prompt_version, model_id)
            pending = [
                candidate for candidate in candidates if candidate.description_hash not in cached
            ]
            if only_hashes is not None:
                pending = [
                    candidate for candidate in pending if candidate.description_hash in only_hashes
                ]
                sampled = list(pending)
            else:
                sampled = _deterministic_sample(pending, effective_rate)
            allowed = min(len(sampled), monthly_remaining)
            if limit is not None:
                allowed = min(allowed, limit)
            selected = sampled[:allowed]
            batches = _chunk(selected, effective_batch_size)

            if dry_run:
                estimated_in, estimated_out = _estimate_tokens(batches)
                cost = self._cost(estimated_in, estimated_out)
                finished_at = datetime.now(tz=UTC)
                return EnrichmentRunResult(
                    run_id=run_id,
                    dry_run=True,
                    candidate_count=len(candidates),
                    cached_count=len(cached),
                    pending_count=len(pending),
                    sampled_count=len(sampled),
                    selected_count=len(selected),
                    batch_count=len(batches),
                    succeeded=0,
                    failed=0,
                    input_tokens=estimated_in,
                    output_tokens=estimated_out,
                    cost_usd=cost,
                    monthly_used_before=monthly_used,
                    monthly_remaining=monthly_remaining,
                    started_at=started_at,
                    finished_at=finished_at,
                )

            enrichments: list[EnrichmentRecord] = []
            requests: list[RequestRecord] = []
            succeeded = 0
            failed = 0
            input_tokens = 0
            output_tokens = 0
            cost_usd = 0.0

            for batch_index, batch in enumerate(batches):
                inputs = _to_inputs(batch)
                result = self._enricher.classify(inputs)
                input_tokens += result.input_tokens
                output_tokens += result.output_tokens
                batch_cost = self._cost(result.input_tokens, result.output_tokens)
                cost_usd += batch_cost

                created_at = datetime.now(tz=UTC).isoformat()
                if result.status == "success":
                    succeeded += len(result.items)
                    enrichments.extend(
                        _records_from_success(
                            batch=batch,
                            result=result,
                            model_id=model_id,
                            prompt_version=prompt_version,
                            taxonomy_version=taxonomy_version,
                            temperature=self._settings.llm_temperature,
                            created_at=created_at,
                        )
                    )
                else:
                    failed += len(batch)
                    enrichments.extend(
                        _records_from_failure(
                            batch=batch,
                            result=result,
                            model_id=model_id,
                            prompt_version=prompt_version,
                            taxonomy_version=taxonomy_version,
                            temperature=self._settings.llm_temperature,
                            created_at=created_at,
                        )
                    )

                requests.append(
                    RequestRecord(
                        request_id=result.request_id,
                        run_id=run_id,
                        model_id=model_id,
                        prompt_version=prompt_version,
                        taxonomy_version=taxonomy_version,
                        batch_index=batch_index,
                        item_count=len(batch),
                        input_tokens=result.input_tokens,
                        output_tokens=result.output_tokens,
                        total_tokens=result.input_tokens + result.output_tokens,
                        cost_usd=round(batch_cost, 8),
                        latency_ms=result.latency_ms,
                        status=result.status,
                        error_message=result.error or "",
                        created_at=created_at,
                    )
                )
                logger.info(
                    "batch enriched",
                    extra={
                        "batch_index": batch_index,
                        "items": len(batch),
                        "status": result.status,
                        "input_tokens": result.input_tokens,
                        "output_tokens": result.output_tokens,
                    },
                )

            self._store.save(enrichments, requests)
            finished_at = datetime.now(tz=UTC)
            return EnrichmentRunResult(
                run_id=run_id,
                dry_run=False,
                candidate_count=len(candidates),
                cached_count=len(cached),
                pending_count=len(pending),
                sampled_count=len(sampled),
                selected_count=len(selected),
                batch_count=len(batches),
                succeeded=succeeded,
                failed=failed,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
                monthly_used_before=monthly_used,
                monthly_remaining=monthly_remaining,
                started_at=started_at,
                finished_at=finished_at,
            )
        finally:
            reset_run_context()

    def _cost(self, input_tokens: int, output_tokens: int) -> float:
        return (
            input_tokens / 1_000_000 * self._settings.llm_input_price_per_million
            + output_tokens / 1_000_000 * self._settings.llm_output_price_per_million
        )


def _deterministic_sample(candidates: Sequence[Candidate], rate: float) -> list[Candidate]:
    if rate >= 1.0:
        return list(candidates)
    if rate <= 0.0:
        return []
    threshold = int(rate * 0xFFFFFFFF)
    return [
        candidate
        for candidate in candidates
        if int(candidate.description_hash[:8], 16) <= threshold
    ]


def _chunk(candidates: Sequence[Candidate], size: int) -> list[list[Candidate]]:
    return [list(candidates[index : index + size]) for index in range(0, len(candidates), size)]


def _to_inputs(batch: Sequence[Candidate]) -> list[EnrichmentInput]:
    return [
        EnrichmentInput(id=candidate.description_hash[:16], description=candidate.description)
        for candidate in batch
    ]


def _records_from_success(
    *,
    batch: Sequence[Candidate],
    result: BatchResult,
    model_id: str,
    prompt_version: str,
    taxonomy_version: str,
    temperature: float,
    created_at: str,
) -> list[EnrichmentRecord]:
    by_id = {candidate.description_hash[:16]: candidate for candidate in batch}
    records: list[EnrichmentRecord] = []
    for item in result.items:
        candidate = by_id.get(item.id)
        if candidate is None:
            continue
        records.append(
            EnrichmentRecord(
                enrichment_id=uuid4().hex,
                description_hash=candidate.description_hash,
                description=candidate.description,
                categoria=item.categoria.value,
                subcategoria=item.subcategoria,
                tipo_objeto=item.tipo_objeto.value,
                confianca=item.confianca,
                justificativa=item.justificativa,
                model_id=model_id,
                prompt_version=prompt_version,
                prompt_hash=PROMPT_HASH,
                taxonomy_version=taxonomy_version,
                temperature=temperature,
                request_id=result.request_id,
                latency_ms=result.latency_ms,
                validation_status="valid",
                validation_errors="",
                created_at=created_at,
            )
        )
    return records


def _records_from_failure(
    *,
    batch: Sequence[Candidate],
    result: BatchResult,
    model_id: str,
    prompt_version: str,
    taxonomy_version: str,
    temperature: float,
    created_at: str,
) -> list[EnrichmentRecord]:
    return [
        EnrichmentRecord(
            enrichment_id=uuid4().hex,
            description_hash=candidate.description_hash,
            description=candidate.description,
            categoria="Outros",
            subcategoria="",
            tipo_objeto="desconhecido",
            confianca=0.0,
            justificativa="",
            model_id=model_id,
            prompt_version=prompt_version,
            prompt_hash=PROMPT_HASH,
            taxonomy_version=taxonomy_version,
            temperature=temperature,
            request_id=result.request_id,
            latency_ms=result.latency_ms,
            validation_status="failed",
            validation_errors=(result.error or "invalid response")[:1000],
            created_at=created_at,
        )
        for candidate in batch
    ]


def _estimate_tokens(batches: Sequence[Sequence[Candidate]]) -> tuple[int, int]:
    input_tokens = 0
    output_tokens = 0
    for batch in batches:
        input_tokens += int((len(SYSTEM_PROMPT) + sum(len(c.description) for c in batch)) / 4)
        output_tokens += 60 * len(batch)
    return input_tokens, output_tokens
