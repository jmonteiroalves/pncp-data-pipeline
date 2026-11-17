"""Gemini client for batched, structured classification."""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from google import genai
from google.genai import types
from pydantic import ValidationError

from pncp_pipeline.enrichment.models import EnrichmentInput, EnrichmentItem, EnrichmentResponse
from pncp_pipeline.enrichment.prompt import (
    RESPONSE_SCHEMA,
    SYSTEM_PROMPT,
    build_user_content,
)
from pncp_pipeline.log import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class BatchResult:
    """Outcome of a single Gemini request, including a repair attempt."""

    items: list[EnrichmentItem]
    status: str
    error: str | None
    request_id: str
    input_tokens: int
    output_tokens: int
    latency_ms: int


class GeminiEnricher:
    """Classify a batch of descriptions with Gemini on Vertex AI."""

    def __init__(
        self,
        *,
        project: str,
        location: str,
        model_id: str,
        temperature: float = 0.0,
        client: Any | None = None,
    ) -> None:
        self._client = client or genai.Client(
            vertexai=True,
            project=project,
            location=location,
        )
        self._model_id = model_id
        self._temperature = temperature

    def classify(self, items: Sequence[EnrichmentInput]) -> BatchResult:
        """Classify a batch and retry once with a repair prompt if invalid."""
        expected_ids = [item.id for item in items]
        contents = build_user_content(items)
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=self._temperature,
            response_mime_type="application/json",
            response_schema=RESPONSE_SCHEMA,
            max_output_tokens=8192,
        )

        started = time.perf_counter()
        input_tokens = 0
        output_tokens = 0
        request_id = uuid4().hex
        last_error = "empty response"

        for attempt in range(2):
            try:
                response = self._client.models.generate_content(
                    model=self._model_id,
                    contents=contents,
                    config=config,
                )
            except Exception as exc:  # network, quota, or safety failure
                logger.exception("gemini request failed", extra={"attempt": attempt + 1})
                return BatchResult(
                    items=[],
                    status="error",
                    error=str(exc),
                    request_id=request_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                )

            request_id = getattr(response, "response_id", None) or request_id
            usage = getattr(response, "usage_metadata", None)
            if usage is not None:
                input_tokens += int(getattr(usage, "prompt_token_count", 0) or 0)
                output_tokens += int(getattr(usage, "candidates_token_count", 0) or 0)

            text = getattr(response, "text", None) or ""
            parsed, error = self._parse(text, expected_ids)
            if error is None and parsed is not None:
                return BatchResult(
                    items=parsed,
                    status="success",
                    error=None,
                    request_id=request_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                )

            last_error = error or "invalid response"
            logger.warning(
                "invalid gemini response",
                extra={"attempt": attempt + 1, "error": last_error},
            )
            if attempt == 0:
                contents = (
                    f"{contents}\n\nSua resposta anterior foi:\n{text}\n\n"
                    f"Ela é inválida: {last_error}\n"
                    "Retorne o JSON corrigido, cobrindo exatamente os mesmos ids."
                )

        return BatchResult(
            items=[],
            status="failed",
            error=last_error,
            request_id=request_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )

    @staticmethod
    def _parse(
        text: str,
        expected_ids: Sequence[str],
    ) -> tuple[list[EnrichmentItem] | None, str | None]:
        try:
            parsed = EnrichmentResponse.model_validate_json(text)
        except ValidationError as exc:
            return None, str(exc)

        ids = [item.id for item in parsed.items]
        if len(ids) != len(set(ids)):
            return None, "duplicate ids in response"
        if set(ids) != set(expected_ids):
            return None, "response ids do not match the request ids"
        return parsed.items, None
