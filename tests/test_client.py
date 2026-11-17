"""Tests for the PNCP HTTP client."""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx
import pytest

from pncp_pipeline.pncp.client import PNCPClient, PNCPError


def _body(
    records: list[dict[str, Any]],
    *,
    page: int = 1,
    total_pages: int = 1,
    remaining: int = 0,
) -> dict[str, Any]:
    return {
        "data": records,
        "totalRegistros": len(records) * total_pages,
        "totalPaginas": total_pages,
        "numeroPagina": page,
        "paginasRestantes": remaining,
    }


def _client(
    handler: Any,
    *,
    max_retries: int = 2,
    sleep: Any = None,
) -> PNCPClient:
    return PNCPClient(
        "https://pncp.gov.br/api/consulta",
        request_interval_seconds=0,
        max_retries=max_retries,
        page_size=50,
        contract_page_size=500,
        timeout_seconds=5,
        transport=httpx.MockTransport(handler),
        sleep=sleep or (lambda _seconds: None),
    )


def test_paginates_across_pages() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["pagina"])
        seen.append(str(request.url))
        records = [{"numeroControlePNCP": f"x-{page}"}]
        return httpx.Response(
            200,
            json=_body(records, page=page, total_pages=2, remaining=1 if page == 1 else 0),
        )

    with _client(handler) as client:
        pages = list(
            client.iter_pages(
                "contratacoes",
                date(2026, 1, 15),
                date(2026, 1, 15),
                modality=6,
            )
        )

    assert [page.page_number for page in pages] == [1, 2]
    assert len(pages) == 2
    assert "codigoModalidadeContratacao=6" in seen[0]
    assert "dataInicial=20260115" in seen[0]


def test_204_ends_pagination() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(204)

    with _client(handler) as client:
        pages = list(
            client.iter_pages("contratacoes", date(2026, 1, 15), date(2026, 1, 15), modality=6)
        )

    assert pages == []


def test_retries_429() -> None:
    sleeps: list[float] = []
    calls = {"count": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(429, headers={"Retry-After": "1"})
        return httpx.Response(200, json=_body([{"id": 1}]))

    with _client(handler, sleep=sleeps.append) as client:
        pages = list(
            client.iter_pages("contratacoes", date(2026, 1, 15), date(2026, 1, 15), modality=6)
        )

    assert calls["count"] == 2
    assert sleeps == [1.0]
    assert len(pages) == 1


def test_raises_after_retry_exhaustion() -> None:
    sleeps: list[float] = []
    calls = {"count": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(500)

    with (
        _client(handler, max_retries=2, sleep=sleeps.append) as client,
        pytest.raises(PNCPError) as error,
    ):
        list(
            client.iter_pages(
                "contratacoes",
                date(2026, 1, 15),
                date(2026, 1, 15),
                modality=6,
            )
        )

    assert calls["count"] == 3
    assert len(sleeps) == 2
    assert error.value.status_code == 500


def test_client_error_is_not_retried() -> None:
    calls = {"count": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(400)

    with _client(handler) as client, pytest.raises(PNCPError) as error:
        list(
            client.iter_pages(
                "contratacoes",
                date(2026, 1, 15),
                date(2026, 1, 15),
                modality=6,
            )
        )

    assert calls["count"] == 1
    assert error.value.status_code == 400


def test_contracts_use_contract_page_size() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json=_body([{"id": 1}]))

    with _client(handler) as client:
        list(client.iter_pages("contratos", date(2026, 1, 15), date(2026, 1, 15)))

    assert "tamanhoPagina=500" in seen[0]
    assert "/v1/contratos?" in seen[0]


def test_modality_is_required_for_notices() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_body([]))

    with _client(handler) as client, pytest.raises(ValueError):
        list(client.iter_pages("contratacoes", date(2026, 1, 15), date(2026, 1, 15)))


def test_page_key_is_deterministic() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_body([{"id": 1, "value": "abc"}]))

    def keys() -> list[str]:
        with _client(handler) as client:
            return [
                page.page_key
                for page in client.iter_pages(
                    "contratacoes",
                    date(2026, 1, 15),
                    date(2026, 1, 15),
                    modality=6,
                )
            ]

    assert keys() == keys()
