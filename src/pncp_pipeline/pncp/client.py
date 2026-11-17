"""HTTP client for the PNCP public consultation API.

The API has no published quota. Empirical tests showed HTTP 429 after a burst
of requests, so the client paces itself and backs off with jitter. A single
worker is intentional: parallelism makes the rate limit harder to control.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime
from typing import Any

import httpx

from pncp_pipeline.hashing import canonical_json, sha256_text
from pncp_pipeline.log import get_logger
from pncp_pipeline.pncp.models import Entity, Mode, Page

logger = get_logger(__name__)

_RETRYABLE_STATUS = frozenset({429})


class PNCPError(RuntimeError):
    """Raised when the PNCP API cannot satisfy a request."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class PNCPClient:
    """Sequential, rate-limited client for the PNCP consultation API."""

    def __init__(
        self,
        base_url: str,
        request_interval_seconds: float = 1.25,
        max_retries: int = 5,
        page_size: int = 50,
        contract_page_size: int = 500,
        timeout_seconds: float = 60.0,
        *,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._interval = request_interval_seconds
        self._max_retries = max_retries
        self._page_size = page_size
        self._contract_page_size = contract_page_size
        self._sleep = sleep
        self._clock = clock
        self._last_request_at = float("-inf")
        self._client = httpx.Client(
            timeout=timeout_seconds,
            transport=transport,
            headers={"User-Agent": "pncp-data-pipeline/0.1"},
        )

    def __enter__(self) -> PNCPClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._client.close()

    def iter_pages(
        self,
        entity: Entity,
        start: date,
        end: date,
        mode: Mode = "publicacao",
        modality: int | None = None,
        start_page: int = 1,
        max_pages: int | None = None,
    ) -> Iterator[Page]:
        """Yield pages for a date window.

        ``mode`` selects publication or update endpoints. Notices require a
        modality code; contracts do not.
        """
        if entity == "contratacoes" and modality is None:
            raise ValueError("modality is required for contratacoes")

        path = self._path(entity, mode)
        page_size = self._page_size if entity == "contratacoes" else self._contract_page_size
        page_number = start_page
        yielded = 0

        while True:
            params: dict[str, Any] = {
                "dataInicial": start.strftime("%Y%m%d"),
                "dataFinal": end.strftime("%Y%m%d"),
                "pagina": page_number,
                "tamanhoPagina": page_size,
            }
            if modality is not None:
                params["codigoModalidadeContratacao"] = modality

            response = self._get(path, params)
            if response is None:
                return

            body = self._decode(response, path, page_number)
            records = body.get("data") or []
            if not isinstance(records, list):
                raise PNCPError(f"unexpected data field for {path} page {page_number}")
            total_records = int(body.get("totalRegistros") or 0)
            total_pages = int(body.get("totalPaginas") or 0)
            remaining = int(body.get("paginasRestantes") or 0)

            if not records:
                return

            yield Page(
                entity=entity,
                endpoint=path,
                mode=mode,
                request_params=dict(params),
                extraction_date=start,
                modality=modality,
                page_number=page_number,
                total_records=total_records,
                total_pages=total_pages,
                status_code=response.status_code,
                records=list(records),
                page_key=self._page_key(path, params, page_number, records),
                ingested_at=datetime.now(tz=UTC),
            )

            yielded += 1
            if max_pages is not None and yielded >= max_pages:
                return
            if remaining == 0:
                return
            if total_pages and page_number >= total_pages:
                return
            page_number += 1

    @staticmethod
    def _path(entity: Entity, mode: Mode) -> str:
        if entity == "contratacoes":
            return f"/v1/contratacoes/{mode}"
        return "/v1/contratos" if mode == "publicacao" else "/v1/contratos/atualizacao"

    @staticmethod
    def _page_key(
        path: str,
        params: dict[str, Any],
        page_number: int,
        records: list[dict[str, Any]],
    ) -> str:
        content_hash = sha256_text(canonical_json(records))
        return sha256_text(f"{path}|{canonical_json(params)}|{page_number}|{content_hash}")

    def _get(self, path: str, params: dict[str, Any]) -> httpx.Response | None:
        url = f"{self._base_url}{path}"
        last_error: Exception | None = None

        for attempt in range(self._max_retries + 1):
            self._throttle()
            try:
                response = self._client.get(url, params=params)
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt >= self._max_retries:
                    raise PNCPError(f"request failed after {attempt + 1} attempts: {exc}") from exc
                self._wait(attempt, None, str(exc), params)
                continue

            if response.status_code == 204:
                return None

            retryable = (
                response.status_code in _RETRYABLE_STATUS or 500 <= response.status_code < 600
            )
            if retryable:
                last_error = PNCPError(
                    f"PNCP returned HTTP {response.status_code}",
                    status_code=response.status_code,
                )
                if attempt >= self._max_retries:
                    raise last_error
                retry_after = self._retry_after(response)
                self._wait(attempt, retry_after, f"HTTP {response.status_code}", params)
                continue

            if response.status_code >= 400:
                raise PNCPError(
                    f"PNCP returned HTTP {response.status_code} for {path}",
                    status_code=response.status_code,
                )

            return response

        raise PNCPError(f"request failed: {last_error}")

    def _decode(
        self,
        response: httpx.Response,
        path: str,
        page_number: int,
    ) -> dict[str, Any]:
        try:
            body = response.json()
        except ValueError as exc:
            raise PNCPError(f"invalid JSON for {path} page {page_number}") from exc
        if not isinstance(body, dict):
            raise PNCPError(f"unexpected payload for {path} page {page_number}")
        return body

    def _throttle(self) -> None:
        now = self._clock()
        wait = self._interval - (now - self._last_request_at)
        if wait > 0:
            self._sleep(wait)
        self._last_request_at = self._clock()

    def _wait(
        self,
        attempt: int,
        retry_after: float | None,
        reason: str,
        params: dict[str, Any],
    ) -> None:
        delay = (
            retry_after
            if retry_after is not None
            else min(2.0**attempt + random.uniform(0.0, 1.0), 60.0)
        )
        logger.warning(
            "retrying PNCP request",
            extra={
                "attempt": attempt + 1,
                "delay_seconds": round(delay, 2),
                "reason": reason,
                "page": params.get("pagina"),
                "modality": params.get("codigoModalidadeContratacao"),
            },
        )
        self._sleep(delay)

    @staticmethod
    def _retry_after(response: httpx.Response) -> float | None:
        value = response.headers.get("Retry-After")
        if value is None:
            return None
        try:
            return max(float(value), 0.0)
        except ValueError:
            return None
