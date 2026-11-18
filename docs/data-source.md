# Data Source

**Decision:** PNCP — Portal Nacional de Contratações Públicas — is the primary source.
**Validated on:** 2026-11-17
**Status:** approved

---

## 1. Requirements

The source must provide:

1. Brazilian public procurement data (notices, contracts, or both).
2. An official, documented API.
3. National coverage, or at least coverage broad enough to be representative.
4. Date-based filters that allow incremental collection.
5. Public access without a paid contract.
6. Enough volume and text quality to support semantic classification.
7. Licensing that allows analysis and publication of derived results.

Nice to have:

- Item-level descriptions.
- Stable identifiers.
- Open data exports for backfill.
- Low or no authentication friction.

---

## 2. Candidates

| Candidate | Operator | Scope | Interface | Authentication |
|---|---|---|---|---|
| **PNCP** | Comitê Gestor da Rede Nacional de Contratações Públicas | Federal, state, municipal | REST/JSON | None for consultation |
| **Compras.gov.br — Dados Abertos** | Ministério da Gestão e da Inovação | Federal | REST/JSON, CSV | None for open modules |
| **Portal da Transparência** | CGU | Federal | REST/JSON | API key |
| **Base dos Dados** | Independent | Curated mirrors | BigQuery, CSV | Google account for BigQuery |

---

## 3. Comparison

| Criterion | PNCP | Compras.gov.br | Portal da Transparência | Base dos Dados |
|---|---|---|---|---|
| Coverage | **National** | Federal only | Federal only | Mirrors public sources |
| Official documentation | Yes, Swagger + integration manual | Yes, Swagger + manuals | Yes | Yes, community docs |
| Authentication | **None** | None for open modules | Required key | Google Cloud |
| Incremental filters | **Publication and update dates** | Publication and inclusion dates | Date filters | Depends on mirror |
| Notices (contratações) | **Yes** | Yes (federal) | Partial | Yes |
| Contracts | **Yes** | Yes (federal) | Yes | Partial |
| Items | No in the consultation API | Endpoint exists but returned no data in tests | No | Partial |
| Observed volume | **~4,000 notices/day** | Not measured | Not measured | Not measured |
| Rate limiting | 429 on bursts | Not measured | API key required | BigQuery quotas |
| Licensing clarity | Public data; site CC BY-ND 3.0 | Open data | Public data | Source-dependent |
| Fit for this project | **High** | Medium | Medium | Low as primary |

### Why not Compras.gov.br as primary

- Covers only federal agencies that use the federal system, which biases any national analysis.
- The PNCP item endpoint is the natural source for item-level descriptions, but it returned **zero records** for every tested date between 2023 and 2026.
- Its catalogue endpoints are excellent and will be used as an optional taxonomy reference.

### Why not Portal da Transparência

- Requires an API key and registration.
- Federal scope only.
- More focused on expenses and transfers than on procurement notices.

### Why not Base dos Dados

- It is a curated mirror, not the source of truth.
- Adds a third-party dependency and does not demonstrate ingestion engineering.
- Useful for cross-validation later.

---

## 4. PNCP in detail

### 4.1 Legal basis and coverage

The PNCP was created by **Lei 14.133/2021** (Nova Lei de Licitações) to centralise the publication of public procurement across the Union, states, municipalities, and the Federal District. Publication in the PNCP is mandatory, which makes it the broadest official source available.

### 4.2 API surface validated

Base URL: `https://pncp.gov.br/api/consulta`

| Operation | Method | Path | Page size |
|---|---|---|---|
| Notices by publication date | GET | `/v1/contratacoes/publicacao` | 10–50 |
| Notices by update date | GET | `/v1/contratacoes/atualizacao` | 10–50 |
| Notice details | GET | `/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}` | — |
| Contracts by publication date | GET | `/v1/contratos` | 10–500 |
| Contracts by update date | GET | `/v1/contratos/atualizacao` | 10–500 |
| Price registry minutes | GET | `/v1/atas` | 10–500 |
| Annual procurement plans | GET | `/v1/pca/*` | 10–500 |

Confirmed by the OpenAPI document at `https://pncp.gov.br/api/consulta/v3/api-docs`.

### 4.3 Authentication

None for consultation. The official open data page states that all searches can be performed without registration or login.

### 4.4 Request format

- Dates: `YYYYMMDD` (validated).
- Pagination: `pagina` starts at 1; `tamanhoPagina` is bounded.
- Empty result: HTTP **204** with no body.
- Errors: 400 for invalid parameters, 422 for semantic errors, 429 for rate limiting, 500 for server errors.

Example:

```bash
curl -sG "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao" \
  --data-urlencode "dataInicial=20260115" \
  --data-urlencode "dataFinal=20260115" \
  --data-urlencode "codigoModalidadeContratacao=6" \
  --data-urlencode "pagina=1" \
  --data-urlencode "tamanhoPagina=50"
```

### 4.5 Observed volume

Test date: **2026-01-15**, a Thursday. Modality codes 1 and 4–12 returned data; codes 2, 3, and 13–15 returned no records that day.

| Measurement | Value |
|---|---|
| Procurement notices | **3,996** |
| Contracts | **6,061** |
| Mean `objetoCompra` length | **207 characters** |
| Median `objetoCompra` length | **183 characters** |
| Notices per page (max) | 50 |

Extrapolated monthly volume:

| Entity | Per day | Per month (30 days) |
|---|---:|---:|
| Notices | ~4,000 | ~120,000 |
| Contracts | ~6,000 | ~180,000 |

These are observations, not guarantees. Volume varies by weekday, seasonality, and reporting behaviour.

### 4.6 Update frequency

Agencies publish and update records continuously. The API exposes two independent date dimensions:

- `dataPublicacaoPncp` — when the notice first appeared.
- `dataAtualizacaoGlobal` — when the record was last changed.

This allows a clean incremental strategy: backfill by publication date, daily delta by update date, and a monthly one-day snapshot for the demo.

### 4.7 Rate limiting — observed behaviour

There is no published quota in the OpenAPI document. Empirical tests on 2026-11-17:

| Test | Result |
|---|---|
| Burst test of 15 requests | 7 calls succeeded, the remaining 8 returned HTTP **429** |
| Sequential requests spaced by 1.2 s | 6 of 6 succeeded |
| Recovery after a 20 s pause | Success |
| 24-page backfill, one day and modality | 1,154 records in ~2 minutes (~4.8 s per page) |
| 118-page delta, three days and one modality | 5,886 records, over 10 minutes, with 429s at pages 8 and 111 |
| 7-day backfill, all modalities | 381 pages, 17,054 new rows, 30m41s |
| `Retry-After` header | Not observed |

**Design consequence:** single worker, token bucket at ~0.8 requests/second,
exponential backoff with jitter, checkpoint per day and modality, and no
parallel ingestion. Long runs must budget for throttling; a 60-minute job
timeout is adequate for a one-day monthly snapshot but not for a 90-day backfill.

### 4.8 Data quality observations

| Observation | Impact | Handling |
|---|---|---|
| `valorTotalHomologado` can be null | Some notices have no awarded value | Keep null; do not coerce to zero |
| Free-text descriptions with platform prefixes | Noise for classification | Strip known prefixes during normalisation |
| Duplicated or near-duplicated descriptions | Wasted LLM calls | Hash-based cache and deduplication |
| Inconsistent capitalisation and accents | Classification noise | Normalise before hashing |
| Nested objects | Parsing complexity | Typed extraction in Silver |
| Occasional encoding artefacts | Broken text | Validate UTF-8; quarantine irrecoverable rows |
| Agencies may correct records after publication | Stale data | 1-day overlap plus a weekly 7-day sweep |

### 4.9 Licensing and attribution

- The procurement data is public, published under the transparency rules of Lei 14.133/2021 and access-to-information legislation.
- The PNCP site content is published under **CC BY-ND 3.0**.
- The project will:
  - attribute PNCP as the source;
  - publish only derived and aggregated data;
  - not redistribute raw payload dumps;
  - keep a link to the original notice whenever a record is displayed.

---

## 5. Secondary source — CATMAT/CATSER catalogue

**API:** `https://dadosabertos.compras.gov.br`

Validated endpoints:

| Module | Endpoint | Result |
|---|---|---|
| Material catalogue | `/modulo-material/4_consultarItemMaterial` | Returns items with group, class, PDM, and description |
| Service catalogue | `/modulo-servico/6_consultarItemServico` | Returns services with section, division, group, class, and description |
| PNCP items | `/modulo-contratacoes/2_consultarItensContratacoes_PNCP_14133` | **0 records** for all tested dates |

The catalogue is useful because it provides an official hierarchy of material and service categories. It can support:

- taxonomy design;
- a deterministic pre-classification when an item code is available;
- a weak label for evaluating the LLM.

It is **not** a dependency in the first version, because the item-level endpoint did not return data.

---

## 6. Decision

Adopt **PNCP as the single primary source** for the first version.

Reasons:

1. National coverage mandated by law.
2. Official, documented, unauthenticated API.
3. Publication and update date filters enable incremental ingestion.
4. Sufficient volume and text richness for the AI use case.
5. Stable natural keys for deduplication and joins.
6. Licensing compatible with derived analysis.

Compras.gov.br remains an optional taxonomy reference. Portal da Transparência and Base dos Dados are out of scope.

---

## 7. Data dictionary (selected fields)

| Field | Type | Description | Use |
|---|---|---|---|
| `numeroControlePNCP` | string | Natural key, format `CNPJ-1-sequence/year` | Primary key |
| `objetoCompra` | string | Free-text purchase description | LLM input |
| `valorTotalEstimado` | numeric | Estimated value | Measure |
| `valorTotalHomologado` | numeric | Awarded value, may be null | Measure |
| `dataPublicacaoPncp` | timestamp | Publication timestamp | Backfill partition |
| `dataAtualizacaoGlobal` | timestamp | Last global update | Incremental watermark |
| `dataAberturaProposta` | timestamp | Proposal opening | Analysis |
| `dataEncerramentoProposta` | timestamp | Proposal closing | Analysis |
| `modalidadeId` | integer | Modality code | Dimension |
| `modalidadeNome` | string | Modality name | Dimension |
| `modoDisputaId` | integer | Dispute mode code | Dimension |
| `situacaoCompraId` | integer | Notice status code | Dimension |
| `situacaoCompraNome` | string | Notice status | Dimension |
| `srp` | boolean | Price registry flag | Analysis |
| `orgaoEntidade.cnpj` | string | Agency CNPJ | Agency key |
| `orgaoEntidade.razaoSocial` | string | Agency name | Dimension |
| `orgaoEntidade.esferaId` | string | Federal, state, municipal | Dimension |
| `orgaoEntidade.poderId` | string | Executive, legislative, judiciary | Dimension |
| `unidadeOrgao.codigoUnidade` | string | Organisational unit code | Unit key |
| `unidadeOrgao.ufSigla` | string | State | Geography |
| `unidadeOrgao.municipioNome` | string | Municipality | Geography |
| `unidadeOrgao.codigoIbge` | string | IBGE municipality code | Geography key |
| `amparoLegal.codigo` | integer | Legal basis code | Dimension |
| `linkProcessoEletronico` | string | Link to the process | Traceability |
| `usuarioNome` | string | Publishing system | Source quality analysis |

---

## 8. Collection plan

### Backfill

- Window: 90 days.
- Endpoint: `/v1/contratacoes/publicacao`.
- Iterate day by day and modality by modality.
- Checkpoint: `(date, modality, page)`.
- Expected duration: several hours at 0.8 req/s; run in 3-day chunks and resume from checkpoints.

### Monthly snapshot

- Scheduled on day 8; the CLI computes the first Tuesday of the month.
- Endpoint: `/v1/contratacoes/publicacao` for that single day, all configured modalities.
- Contracts: `/v1/contratos` for the same day.
- `control.ingestion_runs` records `mode = 'snapshot'`; Gold accepts only successful snapshot dates.
- One day is ~92 pages and fits the 60-minute Cloud Run job timeout.
- The annual reset is a Gold filter for the current calendar year.

### Daily delta (optional)

- Notices: `/v1/contratacoes/atualizacao` with `watermark - 2 days` to today.
- Contracts: `/v1/contratos/atualizacao` with the same window.
- Upsert by natural key.
- Not part of the scheduled path after the monthly snapshot change.

### Watermarks

Stored in `control.watermarks`:

| Source | Entity | Value |
|---|---|---|
| `pncp` | `contratacoes` | Last successful update date |
| `pncp` | `contratos` | Last successful update date |

### Backfill safety

- Do not run backfill, delta, and snapshot at the same time; the local SQLite backend is single-writer.
- Use a separate job invocation with a distinct `run_id`.
- Stop on repeated 429s and resume later from the checkpoint.
- Verify row counts against `totalRegistros` returned by the API.

---

## 9. Risks and open questions

| Risk | Mitigation |
|---|---|
| Undocumented rate limit changes | Conservative pacing, metrics, and alerts |
| API schema changes | Bronze replay, contract tests, versioned extractors |
| Modality codes change | Configuration list validated at runtime; log unknown codes |
| Volume growth | Partitioning, sampling, and query limits |
| Licensing interpretation | Publish derived data only; attribute the source |
| Data corrections by agencies | 1-day overlap and a weekly sweep with idempotent merges |
| Text with personal data | Mask CPF, phone, and e-mail before LLM calls |

Open questions:

- Should the project include contracts in the first release, or notices only?
- Is a 90-day window enough to tell a compelling portfolio story?
- Should the CATMAT/CATSER join be added before or after the first LLM evaluation?
