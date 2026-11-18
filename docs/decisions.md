# Architecture Decision Records

**Last updated:** 2026-11-18

This file records the significant decisions made during the design phase, the alternatives considered, and their consequences. Each decision is dated and has an explicit status.

| ID | Decision | Status |
|---|---|---|
| ADR-001 | PNCP as the primary data source | Accepted |
| ADR-002 | Medallion architecture on GCS and BigQuery | Accepted |
| ADR-003 | Cloud Run Jobs for batch processing | Accepted |
| ADR-004 | dbt Core for transformations | Accepted |
| ADR-005 | Gemini 3.5 Flash-Lite on Vertex AI | Superseded by ADR-015 |
| ADR-006 | Batched structured output with validation | Accepted |
| ADR-007 | US multi-region and us-central1 | Accepted |
| ADR-008 | Terraform and GitHub Actions with Workload Identity Federation | Accepted |
| ADR-009 | No Composer, GKE, Cloud SQL, or Dataflow | Accepted |
| ADR-010 | Deterministic sampling and a 10,000-item monthly cap | Accepted |
| ADR-011 | Defer portfolio site changes until three projects are complete | Accepted |
| ADR-012 | Content-addressed Bronze records partitioned by business date | Accepted |
| ADR-013 | SQLite mirror for local development and tests | Accepted |
| ADR-014 | Backfill in 3-day chunks | Accepted |
| ADR-015 | Switch default model to Gemini 3.1 Flash-Lite | Accepted |
| ADR-016 | Static Git-hosted dashboard instead of Looker Studio | Accepted |
| ADR-017 | Terraform adoption of pre-existing demo resources | Accepted |
| ADR-018 | Monthly first-Tuesday snapshot with annual Gold reset | Accepted |

---

## ADR-001 — PNCP as the primary data source

**Date:** 2026-11-17
**Status:** Accepted

### Context

The project needs a public Brazilian procurement source with broad coverage, an official API, incremental filters, and licensing that allows derived analysis. Candidates were PNCP, Compras.gov.br, Portal da Transparência, and Base dos Dados.

### Decision

Use PNCP as the only primary source for the first version. Keep the Compras.gov.br catalogue as an optional taxonomy reference.

### Rationale

- National coverage mandated by Lei 14.133/2021.
- No authentication for consultation.
- Publication and update date filters.
- Observed volume of ~4,000 notices and ~6,000 contracts per weekday.
- Stable natural key `numeroControlePNCP`.
- Public licensing compatible with derived analysis.

### Alternatives considered

| Alternative | Why rejected |
|---|---|
| Compras.gov.br | Federal-only coverage; item-level endpoint returned no data in tests |
| Portal da Transparência | Requires API key; federal-only; less focused on notices |
| Base dos Dados | Curated mirror; third-party dependency; does not demonstrate ingestion |

### Consequences

- The pipeline must handle aggressive rate limiting (HTTP 429).
- The LLM input is free text, not a controlled vocabulary.
- Item-level analysis is deferred.
- Source attribution is required in the published dashboard and documentation.

---

## ADR-002 — Medallion architecture on GCS and BigQuery

**Date:** 2026-11-17
**Status:** Accepted

### Context

The project needs raw fidelity, replayability, tested transformations, and analytics-ready outputs without introducing unnecessary services.

### Decision

Adopt Bronze, Silver, and Gold layers:

- Bronze: immutable raw objects in Cloud Storage plus native BigQuery tables.
- Silver: typed, deduplicated dbt models.
- Gold: star schema and analytical marts.
- AI and Control datasets for enrichment audit and operations.

### Alternatives considered

| Alternative | Why rejected |
|---|---|
| Direct API to BigQuery | Loses raw payload and replayability |
| Only Silver/Gold | No audit trail for source changes |
| Lakehouse formats (Iceberg, Delta) | Added complexity with no clear benefit at this scale |
| External tables over GCS only | Repeated scanning costs and weaker typing |

### Consequences

- Duplicate storage cost for raw data, kept small by lifecycle rules.
- Clear recovery path from any Silver/Gold defect.
- More tables to govern, mitigated by dbt documentation and tests.

---

## ADR-003 — Cloud Run Jobs for batch processing

**Date:** 2026-11-17
**Status:** Accepted

### Context

The pipeline runs batch jobs daily, with occasional long backfills. The platform must scale to zero and keep operational overhead low.

### Decision

Use Cloud Run Jobs with container images stored in Artifact Registry.

### Alternatives considered

| Alternative | Why rejected |
|---|---|
| Cloud Functions | Short timeout, less control over image and retries |
| GKE | Cluster overhead and cost, explicitly out of scope |
| Compute Engine VMs | Always-on infrastructure |
| Cloud Composer | Managed Airflow is overkill for a linear daily DAG |
| Dataflow | Streaming/beam complexity for a batch REST ingestion |

### Consequences

- One container per job, independently versioned.
- A 60-minute timeout for ingestion; long backfills must be split.
- Minimum billing of one minute per execution, negligible at this volume.
- Local development uses the same Docker image.

---

## ADR-004 — dbt Core for transformations

**Date:** 2026-11-17
**Status:** Accepted

### Context

Transformations need tests, documentation, incremental models, and version control. The project is a portfolio piece for data engineering roles.

### Decision

Use dbt Core with the BigQuery adapter, executed inside a Cloud Run Job.

### Alternatives considered

| Alternative | Why rejected |
|---|---|
| Hand-written SQL in Python | No testing or lineage framework |
| Dataform | Viable, but dbt is more portable and widely adopted |
| dbt Cloud | Paid scheduler; external dependency |
| Stored procedures | Hard to test, review, and document |

### Consequences

- SQL is versioned and reviewed like application code.
- Tests and documentation are first-class.
- The dbt job needs its own service account and permissions.
- dbt artefacts are stored in GCS for documentation hosting.

---

## ADR-005 — Gemini 3.5 Flash-Lite on Vertex AI

**Date:** 2026-11-17
**Status:** Superseded by ADR-015

### Context

The enrichment must classify short Portuguese descriptions into a fixed taxonomy at low cost, with structured output and GCP-native authentication.

### Decision

Use **Gemini 3.5 Flash-Lite** through **Vertex AI**, with `temperature = 0` and a response schema.

### Rationale

- Lowest-cost Gemini tier suitable for classification.
- List price at design time: US$ 0.30 per 1M input tokens and US$ 2.50 per 1M output tokens (batch: US$ 0.15 and US$ 1.25).
- Vertex AI uses IAM and ADC, so no API keys are stored.
- Supports structured output and batch prediction.

### Alternatives considered

| Alternative | Why rejected |
|---|---|
| Gemini API via AI Studio | Manual API key management; free tier may use data for product improvement; rate limits |
| Larger Gemini models | Higher cost with no expected accuracy gain for a 7-class problem |
| Open-source model on Cloud Run | Cold starts, GPU cost, operational burden |
| Keyword rules only | Cannot handle paraphrases and long descriptions |
| BigQuery remote function | Per-row calls, hard to batch, cache, and version |

### Consequences

- The model identifier is pinned in configuration and recorded in every result.
- Prices must be revalidated before implementation and before publication.
- The project must monitor token usage and cost per run.

---

## ADR-006 — Batched structured output with validation

**Date:** 2026-11-17
**Status:** Accepted

### Context

Calling the LLM once per description is expensive and slow. Free-form output is hard to validate and store.

### Decision

Send batches of 20 descriptions per request, require a JSON response schema, and validate every response before storage.

### Validation rules

- Response is valid JSON.
- Every item has an id from the input set.
- The returned id set equals the sent id set.
- Category is in the taxonomy enum.
- Confidence is between 0 and 1.
- Justification is at most 200 characters.

### Failure handling

- One repair attempt with the validation error in the prompt.
- On a second failure, store the record as failed and exclude it from Gold.
- Never overwrite a valid result with an invalid one.

### Alternatives considered

| Alternative | Why rejected |
|---|---|
| One request per description | Higher overhead and cost |
| Free-text output parsed with regex | Brittle and hard to audit |
| Tool calling | More complex than a response schema for this use case |
| No validation | Hallucinations would silently reach the dashboard |

### Consequences

- Cost is dominated by input tokens, so batching is essential.
- Id alignment must be tested explicitly.
- A small percentage of records will remain unclassified until the next run.

---

## ADR-007 — US multi-region and us-central1

**Date:** 2026-11-17
**Status:** Accepted

### Context

The project must minimise cost. Free tiers for Cloud Storage are limited to specific US regions, and BigQuery pricing varies by location.

### Decision

- BigQuery datasets: `US` multi-region.
- Cloud Storage bucket: `us-central1`.
- Cloud Run Jobs: `us-central1`.
- Artifact Registry: `us-central1`.
- Vertex AI: global endpoint for Gemini.

### Alternatives considered

| Alternative | Why rejected |
|---|---|
| São Paulo (`southamerica-east1`) | Higher prices and no GCS free tier; latency is irrelevant for a daily batch |
| US multi-region for GCS | Simpler, but free tier applies only to specific regions |

### Consequences

- Public procurement data leaves Brazil. The project intentionally stores only procurement data, and personal data patterns are masked before any LLM call.
- GCS free tier applies.
- Network latency for the batch is acceptable.
- If data residency becomes a requirement, the architecture can be redeployed to São Paulo with a cost increase.

---

## ADR-008 — Terraform and GitHub Actions with Workload Identity Federation

**Date:** 2026-11-17
**Status:** Accepted

### Context

The project must be reproducible from an empty project and must not store long-lived credentials.

### Decision

- Terraform provisions all GCP resources, with remote state in GCS.
- GitHub Actions runs lint, tests, image build, `terraform plan`, `terraform apply`, and deployment.
- GitHub authenticates to GCP through Workload Identity Federation.

### Alternatives considered

| Alternative | Why rejected |
|---|---|
| Manual console setup | Not reproducible, not reviewable |
| Deployment scripts only | No drift detection or state |
| Service account JSON keys | Long-lived secrets, security risk |
| Cloud Build triggers | Viable, but GitHub Actions keeps CI and CD in one place |

### Consequences

- Terraform state must be protected and versioned.
- The bootstrap of the state bucket and federation pool is manual or uses a small bootstrap module.
- Pull requests show infrastructure diffs before merge.

---

## ADR-009 — No Composer, GKE, Cloud SQL, or Dataflow

**Date:** 2026-11-17
**Status:** Accepted

### Context

The project must prioritise low cost and avoid permanently running infrastructure.

### Decision

Do not use any of those services. Orchestrate with Cloud Scheduler and Cloud Workflows.

### Rationale

| Service | Why not |
|---|---|
| Cloud Composer | Minimum environment cost; overkill for one daily DAG |
| GKE | Cluster management and cost; explicitly excluded |
| Cloud SQL | No relational workload requires a database |
| Dataflow | No streaming or large-scale shuffle requirement |

### Consequences

- Orchestration is limited to the workflow features needed: sequence, retries, branching.
- If the DAG grows substantially, Cloud Workflows can still handle it with subworkflows.
- Operational surface remains small.

---

## ADR-010 — Deterministic sampling and a 10,000-item monthly cap

**Date:** 2026-11-17
**Status:** Accepted

### Context

Classifying every new description would cost around US$ 22 per month at list price. The demo does not need full coverage, but the sample must be reproducible and representative.

### Decision

- Sample by a deterministic hash of the normalised description.
- Cap enrichment at 10,000 unique descriptions per month.
- Cache every result and never re-classify the same text for the same prompt and model version.
- Make the cap and the sampling threshold configurable.

### Alternatives considered

| Alternative | Why rejected |
|---|---|
| Classify everything | Higher cost with limited portfolio benefit |
| Random sample per run | Not reproducible across runs |
| Classify only high-value notices | Biases the category distribution |
| No cap | Risk of runaway cost after a bug |

### Consequences

- Dashboards must label AI-derived metrics as based on a sample.
- Coverage should be reported alongside category totals.
- The cap can be raised after the evaluation shows stable quality.

---

## ADR-011 — Defer portfolio site changes until three projects are complete

**Date:** 2026-11-17
**Status:** Accepted

### Context

The portfolio currently presents four BI-focused projects. The owner plans to develop three data engineering projects and replace the current cases only after all three are complete.

### Decision

Do not modify the portfolio site during this project. Publish this project as a standalone repository and integrate it into the site in a later phase, after the three projects are finished.

### Consequences

- This repository must be self-explanatory without the site.
- The README and docs are written for external readers.
- The site update becomes a separate, later initiative.

---

## ADR-012 — Content-addressed Bronze records partitioned by business date

**Date:** 2026-11-17
**Status:** Accepted

### Context

Re-running an ingestion window must not duplicate rows. Bronze also has to stay
auditable when the source changes a record. Partitioning by ingestion date makes
the same record land in a different partition on every run, which breaks
idempotency and forces full-table MERGE scans.

### Decision

- Compute `record_id` as a SHA-256 of the entity and the canonical record.
- Derive `source_date` from the publication date in the payload, falling back to
  the extraction date.
- Partition Bronze by `source_date`.
- MERGE on `(source_date, record_id)`.

### Alternatives considered

| Alternative | Why rejected |
|---|---|
| Partition by ingestion date | Re-runs create duplicates across partitions |
| MERGE on record id without a partition filter | Scans the whole table for every page |
| One Bronze row per page | Harder to deduplicate individual records |
| Overwrite the ingestion partition | Loses the audit trail of source changes |

### Consequences

- Re-ingesting the same record is a no-op.
- A changed record produces a new row, preserving history.
- Silver still deduplicates by the procurement natural key and keeps the latest version.
- A record whose publication date changes would create a second partition row; this is rare and acceptable for Bronze.

---

## ADR-013 — SQLite mirror for local development and tests

**Date:** 2026-11-17
**Status:** Accepted

### Context

Cloud Storage and BigQuery require credentials and a billed project. The
pipeline still needs an end-to-end path that runs in CI and on a laptop,
including idempotency and checkpoints.

### Decision

Provide local implementations of the Bronze store, loader, and control store:

- raw pages as gzipped JSON Lines under `data/bronze/`;
- Bronze rows, runs, checkpoints, and watermarks in SQLite at `data/local.db`.

Both cloud and local backends share the same row builder and SQL/DDL builders.

### Alternatives considered

| Alternative | Why rejected |
|---|---|
| Emulators for GCS and BigQuery | Extra services, slow CI, incomplete SQL coverage |
| No local persistence | Cannot test idempotency or checkpoints end to end |
| Testcontainers | Heavy for a single-developer portfolio project |
| Mocks only | Would not exercise storage and SQL behaviour |

### Consequences

- CI runs the full ingestion path without GCP.
- The SQLite schema is a mirror, not a byte-for-byte copy; BigQuery-specific
  behaviour is covered by SQL builder tests and must be validated in phase 6.
- Local data lives in `data/` and is ignored by Git and Docker.
- The local backend is single-writer; do not run two local ingestions against the same data directory.

---

## ADR-014 — Backfill in 3-day chunks

**Date:** 2026-11-17
**Status:** Accepted

### Context

The 90-day backfill crosses roughly 7,200 pages. On 2026-11-17, one day of
notices for a single modality took about two minutes for 24 pages (~4.8 s per
page), and a 118-page delta was still throttled after ten minutes. A 7-day
all-modality backfill later completed in 30m41s for 381 pages, but throughput
varied and 429 bursts were frequent. The 60-minute timeout is a hard ceiling,
so the default leaves headroom.

### Decision

- Run backfills in chunks of at most **3 days** per invocation.
- Keep checkpoints per day and modality, so a chunk resumes without rework.
- For the one-off 90-day load, either run 30 chunks or a dedicated job with a
  24-hour timeout.

### Alternatives considered

| Alternative | Why rejected |
|---|---|
| One 90-day job | Far beyond the 60-minute timeout and prone to throttling |
| 7-day chunks | The observed 7-day run fit, but left little headroom under throttling |
| Parallel workers | The API rate limit is the bottleneck; parallelism increases 429s |
| Raise retries only | Does not reduce total runtime; still needs chunking |

### Consequences

- More invocations, but each is cheap and restartable.
- The observed 7-day run fits, but automated backfills still use 3-day chunks.
- The daily delta is unaffected; it uses a short window.
- The scheduler can launch chunks sequentially during the initial load.

---

## ADR-015 — Switch default model to Gemini 3.1 Flash-Lite

**Date:** 2026-11-17
**Status:** Accepted

### Context

The pilot evaluation compared two Flash-Lite models on the same 50 labelled
descriptions and measured the actual token usage of the enrichment pipeline.

| Model | Macro-F1 | Cost per 1,000 items |
|---|---:|---:|
| Gemini 3.5 Flash-Lite | 0.874 | ~US$ 0.27 |
| Gemini 3.1 Flash-Lite | 0.865 | ~US$ 0.17 |

Both pass the release gate of 0.85. The original cost target was US$ 0.25 per
1,000 items; 3.5 exceeded it with the current prompt, while 3.1 stayed below.

### Decision

Use `gemini-3.1-flash-lite` as the default model and set the price assumptions
to US$ 0.25 input and US$ 1.50 output per 1M tokens.

### Alternatives considered

| Alternative | Why rejected |
|---|---|
| Keep 3.5 | Higher cost for a 0.009 macro-F1 gain; over the target |
| Shorten the justification to cut output tokens | Loses auditability and only partially closes the gap |
| Use the Batch API | Good future optimisation, but adds latency and input/output plumbing |
| Use a larger model | Unnecessary for a seven-class problem and far more expensive |

### Consequences

- Enrichment cost is about US$ 0.17 per 1,000 items in the pilot.
- Quality is slightly lower but still above the gate.
- `model_id` is stored per row, so both models can coexist and be compared.
- Re-evaluate when the full 300-label golden set is reviewed or the prompt changes.

---

## ADR-016 — Static Git-hosted dashboard instead of Looker Studio

**Date:** 2026-11-17
**Status:** Accepted

### Context

Phase 5 needs a public dashboard for the portfolio. The original design used
Looker Studio. During implementation:

- The Looker Studio API only searches and manages existing assets; it cannot
  create reports or charts.
- The API requires a Google Workspace or Cloud Identity organization with
  domain-wide delegation, and the project account is a personal Gmail account.
- A manual report would not be reproducible from the repository and would need
  browser work outside the codebase.

### Decision

Deliver a static dashboard (`docs/dashboard/`) built with Chart.js and served by
GitHub Pages. A Python export script queries the Gold marts and writes an
aggregated `data.json`. Looker Studio remains documented as an optional manual
setup against the same Gold tables.

### Alternatives considered

| Alternative | Why rejected |
|---|---|
| Manual Looker Studio report | Not reproducible; no API for report creation |
| Looker Studio embedding | Still requires a manually built report |
| Streamlit on Cloud Run | Adds a running service and cost for a demo |
| Notebook screenshot | Not interactive or linkable |

### Consequences

- The dashboard is public, free, and versioned with the code.
- Refreshes are explicit: run the export script and commit `data.json`.
- Interactivity is limited to chart tooltips; no date/category filters yet.
- A scheduled refresh can be added in phase 6 with GitHub Actions.
- The Looker Studio path remains available for a future enterprise version.

---

## ADR-017 — Terraform adoption of pre-existing demo resources

**Date:** 2026-11-17
**Status:** Accepted

### Context

The project, lake bucket, BigQuery datasets, and budget existed before Terraform
was introduced. A fresh `terraform apply` must also remain possible for a new
environment. Cloud Run Jobs validate that their container image exists, so
images must be pushed before the job resources are created.

### Decision

- Use a `bootstrap/` root with local state to create the GCS state bucket,
  Workload Identity Federation, and deploy service account.
- Import the existing lake bucket and five BigQuery datasets into the main
  remote state.
- Keep the billing budget in the billing console, outside the deploy service
  account, to avoid granting billing-account administration to CI.
- Build and push images in GitHub Actions before `terraform apply`; pass the
  commit SHA as `image_tag`.

### Alternatives considered

| Alternative | Why rejected |
|---|---|
| Destroy and recreate the existing resources | Deletes the demo data and dashboard source |
| Terraform `import` blocks | Fail on a fresh project, which would break reproducibility |
| Give the deploy service account billing admin | Broader than needed for a demo |
| Apply jobs with a placeholder image | Adds a second apply and a fragile bootstrap path |

### Consequences

- The current environment is managed by Terraform and the code still supports a
  clean project.
- Bootstrap uses local state; it is run once and documented.
- Budget alerts remain a manual account-level guardrail.
- A CI deploy always pushes both images before applying, so job updates are
  atomic from the pipeline's perspective.

---

## ADR-018 — Monthly first-Tuesday snapshot with annual Gold reset

**Date:** 2026-11-18
**Status:** Accepted

### Context

The portfolio demo does not need daily freshness or complete coverage to prove
the architecture. A 15-day refresh would require about 1,380 API pages and,
with the current per-page BigQuery load, roughly seven hours. A single day is
about 92 pages and fits the 60-minute job timeout without redesigning ingestion.

### Decision

- Run one **monthly snapshot** on the **first Tuesday** of the month.
- Trigger it on **day 8** at 03:00 BRT; the job computes the first Tuesday and
  skips if that snapshot already succeeded.
- Snapshot one publication day for notices and contracts, all configured modalities.
- Gold facts accept only dates with a successful `snapshot` run in
  `control.ingestion_runs`, and only the current calendar year.
- Gold tables are table models and are rebuilt each run, so the January run
  removes the previous year.
- The dashboard compares monthly snapshots rather than daily continuity.
- The stale-data alert was removed: a monthly cadence cannot be expressed with
  Cloud Monitoring's 23h30m maximum absence window. Job-error alerts cover failures.

### Alternatives considered

| Alternative | Why rejected |
|---|---|
| Daily ingestion | More cost and freshness than the demo needs |
| Every 15 days | ~7 hours of ingestion at the current per-page load |
| Weekly Tuesday | ~US$ 3/month and 52 snapshots; more than necessary |
| One day per quarter | Panel could look stale for months |
| Keep all history | Storage and cost grow without portfolio benefit |

### Consequences

- Cost is roughly US$ 0.70/month at 4,000 monthly classifications.
- One snapshot run takes about 30–40 minutes.
- The dashboard shows one point per month; it is an architectural sample, not a
  continuous national trend.
- A failed snapshot does not create the success marker that Gold requires, so
  the date stays out of the dashboard until a run succeeds.
- The annual reset is automatic through the current-year filter.
- A manual backfill or delta can still be run, but its dates are not displayed
  unless they are recorded as snapshots.
