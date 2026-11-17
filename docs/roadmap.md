# Roadmap

**Status:** phases 0–4 complete with a pilot evaluation; phase 5 pending
**Last updated:** 2026-11-17

---

## 1. Overview

| Phase | Focus | Effort (part-time) | Depends on |
|---|---|---:|---|
| 0 | Design and data source validation | done | — |
| 1 | Repository scaffold and local tooling | 1–2 days | Phase 0 |
| 2 | Ingestion and Bronze layer | 4–6 days | Phase 1 |
| 3 | Silver models with dbt | 4–5 days | Phase 2 |
| 4 | LLM enrichment and evaluation | 5–7 days | Phase 3 |
| 5 | Gold marts and dashboard | 4–6 days | Phase 4 |
| 6 | Terraform and CI/CD | 4–6 days | Phase 5 |
| 7 | Observability and cost controls | 2–3 days | Phase 6 |
| **Total** | | **24–35 days** | |

Effort assumes one developer working part-time, with no prior code in the repository.

---

## 2. Phase 0 — Design and validation

**Status:** complete.

### Deliverables

- Data source comparison and validation.
- Architecture with Medallion layers.
- AI strategy and taxonomy.
- Data model for Bronze, Silver, AI, Gold, and Control.
- Cost estimate.
- Architecture Decision Records.

### Acceptance criteria

- [x] PNCP API validated with real requests.
- [x] Volume, pagination, and rate limiting observed and documented.
- [x] Alternatives compared and rejected with reasons.
- [x] Cost estimate has explicit assumptions and sources.
- [x] Documentation approved.

---

## 3. Phase 1 — Repository scaffold and local tooling

### Tasks

- Create the Python project with `pyproject.toml`.
- Add `ruff`, `pytest`, `mypy` (or `pyright`), and `pre-commit`.
- Create the `Dockerfile` used by all Cloud Run Jobs.
- Create a `Makefile` with `setup`, `lint`, `test`, `build`, `run-local`.
- Add `.gitignore`, `.dockerignore`, and `.env.example`.
- Add a GitHub Actions workflow for lint and tests.
- Add the base folder structure: `src/`, `tests/`, `dbt/`, `infra/`.
- Add a minimal structured logging module.
- Add the configuration loader with environment variables and validation.

### Acceptance criteria

- [x] `make setup` installs dependencies in a clean environment.
- [x] `make lint` and `make test` pass locally.
- [x] `docker build` produces an image under 500 MB (269 MiB on 2026-11-17).
- [x] CI runs lint and tests on every pull request (first run green on 2026-11-17).
- [x] No secrets are required to run the tests.
- [x] README explains how to run the project locally.

The container build was verified locally on 2026-11-17: 269 MiB, below the
500 MB CI budget. The first CI run passed on 2026-11-17.

---

## 4. Phase 2 — Ingestion and Bronze layer

### Tasks

- Implement the PNCP client:
  - token bucket at 0.8 requests/second;
  - exponential backoff with jitter for 429 and 5xx;
  - HTTP 204 handling;
  - configurable page size.
- Implement modality configuration and validation.
- Implement the GCS writer with deterministic object paths and gzip.
- Implement the BigQuery loader for Bronze.
- Create the Control tables: `ingestion_runs`, `ingestion_checkpoints`, `watermarks`.
- Implement checkpoint and resume.
- Implement backfill by publication date.
- Implement daily delta by update date with a 1-day overlap and a weekly sweep.
- Implement contract ingestion.
- Add idempotent `MERGE` on `(source_date, record_id)`.
- Add unit tests with mocked HTTP responses.
- Add an opt-in integration test against the live API.
- Add a local backend with SQLite and gzipped files for development and CI.
- Handle SIGTERM so an interrupted run is recorded as failed.
- Compare fetched counts with the API `totalRegistros` and warn on mismatch.

### Acceptance criteria

- [x] A 7-day backfill completes for all configured modalities.
- [x] Row counts reconcile with the API `totalRegistros` (1,154 notices for modality 6 on 2026-01-15).
- [x] Re-running the same window produces no duplicate Bronze rows (local backend).
- [x] A simulated 429 is retried and logged.
- [x] An interrupted job resumes from the last checkpoint.
- [ ] Every Cloud Storage object has a matching Bronze record (local equivalent verified; cloud path awaits a project).
- [x] A run can be traced from `run_id` to the raw object and to the Bronze rows.
- [x] A 7-day backfill completes within the 60-minute job timeout (30m41s for 381 pages).

Live validation on 2026-11-17 showed that the API throttles aggressively on long
runs. A 24-page day for one modality took about two minutes; a 118-page delta
took over ten minutes. The 7-day all-modality backfill is therefore executed in
3-day chunks, not as a single job. The 60-minute criterion applies to a chunk,
not to the full history.

Local validation also confirmed:

- 1,154 notices and 24 pages for modality 6 on 2026-01-15, matching the API
  `totalRegistros`.
- 500 contracts loaded from a single page with the 500-record page size.
- Re-running the completed day skipped it through the checkpoint.
- The 7-day backfill of 9–15 January 2026 completed in **30m41s**, across
  **381 pages**, loading **17,054 new Bronze rows**. One already-completed
  day/modality was skipped through the checkpoint.
- 43 automated tests pass, including mocked 429, retry, pagination, and MERGE
  behaviour.

---

## 5. Phase 3 — Silver models with dbt

### Tasks

- Create the dbt project and profile.
- Build staging models for notices and contracts.
- Parse nested JSON into typed columns.
- Normalise dates, currency, CNPJ, UF, and IBGE codes.
- Deduplicate by natural key.
- Build conformed dimensions: agency, unit, modality, legal basis.
- Build `fato`-ready intermediate models.
- Add a quarantine model and reason codes.
- Add generic and singular tests.
- Generate and publish dbt documentation.
- Configure incremental materialisations.
- Add a dbt Cloud Run Job.

### Acceptance criteria

- [x] `dbt build` passes from scratch on the dev dataset (44/44 nodes).
- [x] `numero_controle_pncp` is unique in Silver.
- [x] All foreign keys resolve.
- [x] No negative monetary values.
- [x] Null rate for `objeto_compra` is below 2% (0% in the current sample).
- [x] Quarantine rate is below 1% (0 rows in the current sample).
- [x] dbt docs are generated (hosting in phase 6).
- [x] A full refresh completes within 15 minutes (about 34 seconds).
- [x] Model and key column descriptions exist for every public model.

Validated against BigQuery on 2026-11-17: 2,206 notices and 500 contracts in
Silver, 44/44 dbt nodes passing, 0 null purchase descriptions, 0 quarantined
rows in the current sample, and a full build in about 34 seconds. dbt docs are
generated locally; hosting is part of phase 6.

---

## 6. Phase 4 — LLM enrichment and evaluation

### Tasks

- Define the taxonomy and version it.
- Write the prompt with definitions and few-shot examples.
- Implement the Gemini client on Vertex AI.
- Implement normalisation and PII masking.
- Implement deterministic sampling and the monthly cap.
- Implement batching of 20 items.
- Implement the response schema and validation.
- Implement the repair retry.
- Implement the cache.
- Create `ai.classificacao` and `control.llm_requests`.
- Implement dry-run with token estimates.
- Build a 300-item golden-set template and a labelled 50-item pilot.
- Implement the evaluation script with accuracy, macro-F1, and a confusion matrix.
- Implement a keyword baseline for comparison.

### Acceptance criteria

- [x] 100% of responses accepted into Gold pass schema validation; invalid responses exist only in the audit table with a failure status.
- [x] The returned id set always matches the sent id set.
- [x] Re-running the job performs zero new LLM calls for cached items.
- [x] Macro-F1 on the pilot golden set is at least 0.85 (0.865 with Gemini 3.1 Flash-Lite).
- [x] The keyword baseline is measured and reported (0.656 macro-F1).
- [x] Cost per 1,000 classifications is at or below US$ 0.25 (measured US$ 0.172).
- [x] No CPF, phone number, or e-mail appears in a prompt (masking tested).
- [x] Invalid responses are stored with a reason and do not reach Gold.
- [x] Model, prompt, and taxonomy versions are recorded in every row.
- [x] A dry run reports request count and token estimate without spending.

The evaluation uses a **50-item pilot** labelled for this phase. The 300-item
template is in `evaluation/golden_set.csv` and still needs owner review before
the macro-F1 gate is considered final. The pilot result is 0.865 versus 0.656
for the keyword baseline. Gemini 3.1 Flash-Lite replaced 3.5 after the
cost/quality comparison (ADR-015).

---

## 7. Phase 5 — Gold marts and dashboard

### Tasks

- Build the star schema: `fato_contratacao`, `fato_contrato`, and dimensions.
- Build the latest-classification model.
- Build analytical marts:
  - spend by category;
  - top agencies;
  - monthly trend;
  - geographic distribution;
  - classification coverage.
- Add tests for relationships and accepted values.
- Build the Looker Studio dashboard with four pages:
  - overview;
  - categories;
  - agencies;
  - data quality and AI coverage.
- Capture screenshots for the README.
- Write the narrative for the portfolio case.

### Acceptance criteria

- [ ] Gold totals reconcile with Silver within 0.1%.
- [ ] Every fact row has a valid date and agency.
- [ ] Classification coverage is displayed next to AI-derived metrics.
- [ ] Dashboard loads in under 5 seconds.
- [ ] Dashboard queries stay within the monthly byte limit.
- [ ] Four pages are published and accessible by link.
- [ ] Screenshots and insights are added to the README.

---

## 8. Phase 6 — Terraform and CI/CD

### Tasks

- Create Terraform modules for:
  - APIs;
  - service accounts and IAM;
  - GCS bucket and lifecycle;
  - BigQuery datasets and tables;
  - Artifact Registry;
  - Cloud Run Jobs;
  - Cloud Scheduler;
  - Cloud Workflows;
  - budgets and alerts.
- Configure remote state in GCS.
- Create the bootstrap module for state and federation.
- Configure Workload Identity Federation for GitHub.
- Create GitHub Actions workflows for:
  - pull request: lint, test, plan;
  - main: build, push, apply, deploy.
- Document rollback.

### Acceptance criteria

- [ ] `terraform apply` succeeds from an empty project.
- [ ] `terraform plan` is clean after apply.
- [ ] No service account keys exist.
- [ ] GitHub Actions authenticates through federation.
- [ ] A pull request shows an infrastructure diff.
- [ ] A merge to main deploys the new image and job revision.
- [ ] Rollback to the previous image tag is documented and tested.
- [ ] `terraform destroy` removes all billable resources.

---

## 9. Phase 7 — Observability and cost controls

### Tasks

- Create log-based metrics for failures, 429s, and invalid LLM responses.
- Create alert policies for job failure and stale data.
- Create budget alerts at 50%, 90%, and 100%.
- Add `maximum_bytes_billed` to dashboard and dbt queries.
- Build an operations dashboard.
- Write a runbook covering:
  - 429 storms;
  - schema drift;
  - partial loads;
  - LLM outage;
  - budget exhaustion;
  - rollback.
- Simulate at least three failures and validate the alerts.

### Acceptance criteria

- [ ] A failed job triggers an alert within 5 minutes.
- [ ] Missing data for 26 hours triggers an alert.
- [ ] A budget threshold triggers a notification.
- [ ] The runbook steps are validated at least once.
- [ ] The operations dashboard shows runs, rows, errors, and cost.
- [ ] Monthly cost stays below US$ 10.

---

## 10. Definition of Done

A phase is done only when:

1. Code is merged and CI is green.
2. Tests cover the new behaviour.
3. Documentation is updated.
4. The change is reproducible locally.
5. No secret is committed.
6. Cost impact is understood.
7. The acceptance criteria for the phase are met.

---

## 11. Milestones

| Milestone | Meaning | Phase |
|---|---|---|
| M1 | A full week of PNCP data is in Bronze and can be replayed | 2 |
| M2 | Silver is trusted, tested, and documented | 3 |
| M3 | The LLM reaches the quality gate | 4 |
| M4 | The dashboard tells a coherent story | 5 |
| M5 | The stack is reproducible from an empty project | 6 |
| M6 | The pipeline is observable and cost-controlled | 7 |

---

## 12. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Rate limiting slows the backfill | High | Medium | Checkpoints, 0.8 req/s, split by month |
| API schema drift | Medium | High | Bronze replay, contract tests, quarantine |
| LLM accuracy below target | Medium | High | Golden set, few-shot examples, model comparison, taxonomy tuning |
| Cost overrun from retries | Low | Medium | Caps, cache, dry run, budget alerts |
| Terraform bootstrap friction | Medium | Medium | Small bootstrap module, documented steps |
| Dashboard query cost | Low | Medium | Partition pruning, `maximum_bytes_billed`, pre-aggregated marts |
| Scope creep into item-level data | Medium | Medium | Deferred backlog, explicit non-goals |

---

## 13. Deferred backlog

These items are intentionally out of scope for the first release:

- Vertex AI Batch API for a 50% discount.
- CATMAT/CATSER deterministic pre-classification.
- Item-level procurement data.
- SCD2 snapshots for contracts.
- Embedding-based deduplication of descriptions.
- Public API or export for third parties.
- Multi-language taxonomy.
- Automated cost anomaly detection.
- Batch Bronze loads per day to cut BigQuery job overhead (observed ~18 s/page in the cloud path).
- Real-time ingestion.

---

## 14. Portfolio integration

The portfolio site will not be changed during this project. Integration is deferred until three data engineering projects are complete, as recorded in ADR-011.

When that phase starts, the site will need:

- a new project card with a short case study;
- links to the repository and dashboard;
- two or three screenshots;
- a clear description of the problem, architecture, and results;
- a decision on whether the four current BI cases are replaced or archived.

---

## 15. Next step

Start phase 1:

1. Confirm the GitHub repository name and owner.
2. Create the GCP project and enable billing.
3. Configure the budget alert before deploying anything.
4. Create the Python scaffold and CI.
5. Run the first 7-day ingestion in phase 2.
