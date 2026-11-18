# Cost Estimation

**Scenario:** demonstration and portfolio environment
**Currency:** USD, list prices, excluding taxes
**Reference date:** 2026-11-17
**Status:** approved

---

## 1. Scope

This estimate covers the monthly operating cost of the pipeline described in [architecture.md](architecture.md):

- a monthly one-day snapshot from PNCP;
- storage in Cloud Storage and BigQuery;
- dbt transformations;
- LLM enrichment of a sampled subset;
- orchestration, logging, and container storage.

It does not cover:

- one-time development effort;
- taxes, currency conversion, or IOF;
- a custom domain;
- paid BI licences;
- the US$ 300 new-customer trial credit, which is treated as a separate benefit.

---

## 2. Assumptions

| Assumption | Value | Rationale |
|---|---|---|
| Operating mode | One monthly snapshot (first Tuesday) | Demo does not need daily freshness |
| Historical backfill | 90 days, ad-hoc only | Optional; not part of the schedule |
| Notices per snapshot | ~4,000 | 3,996 observed on a weekday |
| Contracts per snapshot | ~6,000 | 6,061 observed on a weekday |
| BigQuery logical storage | ~1 GiB | Current-year snapshots only |
| Cloud Storage | ~1 GiB compressed | JSONL gzip, lifecycle after 180 days |
| Bytes scanned per month | ~10 GB | Monthly dbt run and dashboard export |
| Pipeline runs | 1 per month | Day 8, first Tuesday snapshot |
| Enrichment volume | ~4,000 unique descriptions per month | All new descriptions in the snapshot |
| Items per LLM request | 20 | Balances overhead and output reliability |
| Input tokens per item | 137 | Measured on a 20-item batch |
| Output tokens per item | 92 | Measured; includes category, subcategory, confidence, and justification |
| Region | BigQuery `US`, GCS and Cloud Run `us-central1` | Free-tier eligibility and lowest list prices |
| Model | Gemini 3.1 Flash-Lite, Vertex AI, global endpoint | Lowest-cost tier that met the quality gate |

Volumes are estimates based on a single weekday sample. They are sufficient for budgeting, not for capacity guarantees.

### 2.1 Free, conditionally free, and paid services

| Classification | Services | Note |
|---|---|---|
| **Free within limits** | Cloud Scheduler (3 jobs), Cloud Workflows (5,000 steps), Cloud Logging (50 GiB) | No charge if the usage stays below the monthly limit |
| **Conditionally free** | Cloud Storage, BigQuery, Cloud Run Jobs, Artifact Registry | Free only in specific regions or under specific usage limits, aggregated per billing account |
| **Paid** | Vertex AI Gemini | No free tier for these models; the expected bill is almost entirely here |
| **Free product** | GitHub Pages (static dashboard) | No hosting cost; Looker Studio remains an optional free path |

The expected bill is therefore **not zero**, even though most infrastructure stays inside free tiers. The paid component is the LLM.

---

## 3. Unit prices

| Service | SKU | Price | Free tier |
|---|---|---|---|
| BigQuery | On-demand queries | US$ 6.25 per TiB | First 1 TiB per month per account |
| BigQuery | Active logical storage | US$ 0.000031507 per GiB-hour (~US$ 0.023 per GiB-month) | First 10 GiB per month |
| Cloud Storage | Standard storage, regional | US$ 0.000027397 per GiB-hour (~US$ 0.020 per GiB-month) | 5 GB-month in us-central1, us-east1, or us-west1 |
| Cloud Storage | Class A operations | US$ 0.005 per 1,000 | 5,000 per month |
| Cloud Storage | Class B operations | US$ 0.0004 per 1,000 | 50,000 per month |
| Cloud Run Jobs | CPU | US$ 0.000018 per vCPU-second | 240,000 vCPU-seconds per month |
| Cloud Run Jobs | Memory | US$ 0.000002 per GiB-second | 450,000 GiB-seconds per month |
| Cloud Scheduler | Jobs | US$ 0.10 per job per month above the free tier | 3 jobs per account |
| Cloud Workflows | Internal steps | US$ 0.01 per 1,000 steps | 5,000 steps per month |
| Artifact Registry | Storage | US$ 0.000136986 per GiB-hour (~US$ 0.10 per GiB-month) | 0.5 GiB-month |
| Cloud Logging | Log storage | US$ 0.50 per GiB above the free tier | First 50 GiB per project per month |
| Vertex AI | Gemini 3.1 Flash-Lite input | US$ 0.25 per 1M tokens | None |
| Vertex AI | Gemini 3.1 Flash-Lite output | US$ 1.50 per 1M tokens | None |
| Vertex AI | Gemini 3.1 Flash-Lite batch input | US$ 0.125 per 1M tokens | None |
| Vertex AI | Gemini 3.1 Flash-Lite batch output | US$ 0.75 per 1M tokens | None |

Sources, accessed on 2026-11-17:

- BigQuery: <https://cloud.google.com/bigquery/pricing>
- Cloud Storage: <https://cloud.google.com/storage/pricing>
- Cloud Run: <https://cloud.google.com/run/pricing>
- Cloud Scheduler: <https://cloud.google.com/scheduler/pricing>
- Cloud Workflows: <https://cloud.google.com/workflows/pricing>
- Artifact Registry: <https://cloud.google.com/artifact-registry/pricing>
- Cloud Logging: <https://cloud.google.com/logging/pricing>
- Vertex AI: <https://cloud.google.com/vertex-ai/generative-ai/pricing>

Prices change. Revalidate before implementation and before publishing the estimate.

---

## 4. Monthly estimate

### 4.1 Compute and storage

| Service | Estimated usage | Free tier applied | Estimated cost |
|---|---|---|---|
| Cloud Storage — storage | 1 GiB | 5 GB | US$ 0.00 |
| Cloud Storage — operations | < 5,000 Class A, < 50,000 Class B | Yes | US$ 0.00 |
| BigQuery — storage | 5 GiB | 10 GiB | US$ 0.00 |
| BigQuery — queries | 10 GB scanned | 1 TiB | US$ 0.00 |
| Cloud Run Jobs — ingestion | 1,800 vCPU-s, 1,800 GiB-s | 240,000 / 450,000 | US$ 0.00 |
| Cloud Run Jobs — dbt | 300 vCPU-s, 300 GiB-s | Shared with above | US$ 0.00 |
| Cloud Run Jobs — enrichment | 600 vCPU-s, 600 GiB-s | Shared with above | US$ 0.00 |
| Cloud Scheduler | 3 jobs | 3 jobs | US$ 0.00 |
| Cloud Workflows | ~1,200 internal steps | 5,000 steps | US$ 0.00 |
| Artifact Registry | 0.6 GiB | 0.5 GiB | US$ 0.01 |
| Cloud Logging | < 1 GiB | 50 GiB | US$ 0.00 |
| **Subtotal** | | | **US$ 0.01** |

Cloud Run calculation: one monthly run × (30 min ingestion + 5 min dbt + 10 min enrichment) = 45 minutes = 2,700 seconds, with 1 vCPU and 1 GiB per job.

### 4.2 AI enrichment

Formula:

```text
cost = items × (input_tokens × input_price + output_tokens × output_price) / 1,000,000
```

With 137 input tokens and 92 output tokens per item:

| Component | Calculation | Cost |
|---|---|---|
| Input | 4,000 × 137 × US$ 0.25 / 1,000,000 | US$ 0.14 |
| Output | 4,000 × 92 × US$ 1.50 / 1,000,000 | US$ 0.55 |
| **Total** | | **US$ 0.69** |

### 4.3 Total

| Block | Cost |
|---|---|
| Compute and storage | US$ 0.01 |
| AI enrichment | US$ 0.69 |
| **Monthly total** | **US$ 0.70** |

Rounded budget: **US$ 1 per month** for the demo, with a **US$ 10 budget alert threshold** as a safety margin. The measured cost in the pilot was **US$ 0.172 per 1,000 items**.

---

## 5. Sensitivity

### 5.1 Enrichment volume

| Monthly classifications | Standard cost | Batch API cost |
|---:|---:|---:|
| 1,000 | US$ 0.17 | US$ 0.09 |
| 4,000 (monthly snapshot) | US$ 0.69 | US$ 0.35 |
| 10,000 (monthly cap) | US$ 1.72 | US$ 0.86 |
| 60,000 | US$ 10.34 | US$ 5.17 |
| 120,000 (full coverage) | US$ 20.67 | US$ 10.34 |

### 5.2 One-time backfill

| Item | Value |
|---|---|
| Days | 90 |
| Notices | ~360,000 |
| Contracts | ~545,000 |
| Raw storage | ~2 GB uncompressed, under 1 GB compressed |
| API requests | ~8,300 at 50 and 500 records per page |
| Estimated duration | 3–5 hours at 0.8 requests per second, split into multiple runs |
| Sampled classifications | 20,000 |
| LLM cost, standard | US$ 3.44 |
| LLM cost, batch | US$ 1.72 |

### 5.3 What could change the estimate

| Factor | Effect |
|---|---|
| Full coverage instead of a 10,000-item cap | +US$ 20 per month |
| Retry rate of 5% on LLM calls | +~US$ 0.09 per month |
| Dashboard queries without partition pruning | Could exhaust the 1 TiB free tier in extreme cases |
| A larger dbt project with many full refreshes | More bytes scanned; still likely within the free tier |
| Storage kept beyond 180 days | Still small, but outside the free tier after 10 GiB |
| Movement to São Paulo | Higher compute prices and no GCS free tier |

---

## 6. Free-tier caveats

Free tiers are not a guarantee of a zero bill.

1. **Account-level aggregation.** Cloud Run, Scheduler, Workflows, and Artifact Registry free tiers apply per billing account, not per project.
2. **Region restrictions.** The 5 GB Cloud Storage free tier applies only to `us-central1`, `us-east1`, and `us-west1`.
3. **BigQuery query free tier.** The first 1 TiB per month applies to on-demand pricing. Capacity pricing or editions have different rules.
4. **Vertex AI has no free tier** for these models. The LLM cost is real.
5. **Minimum billing.** Cloud Run Jobs bill at least one minute per instance.
6. **Network egress.** Internet egress is not included in this estimate. The static dashboard is served by GitHub Pages, so it does not generate GCP egress.
7. **Backfill month operations.** The one-time backfill writes roughly 8,300 objects, which can exceed the 5,000 free Class A operations by a few thousand. The additional cost is below US$ 0.02.
8. **Price changes.** All figures must be revalidated before implementation.

The US$ 300 new-customer trial credit covers the first months of this project with a large margin, but the estimate above assumes a paid account.

---

## 7. Cost controls

| Control | Implementation |
|---|---|
| Budget | US$ 10 per month, alerts at 50%, 90%, and 100% |
| LLM cap | 10,000 unique descriptions per month |
| LLM cache | Never re-classify the same text for the same prompt and model version |
| Dry run | Estimate requests and tokens without calling the API |
| Per-run limits | Maximum items, calls, and output tokens |
| BigQuery guard | `maximum_bytes_billed` on dashboard queries and dbt runs |
| Partitioning | All fact tables partitioned by date |
| Clustering | By agency and category where useful |
| Lifecycle | Raw GCS objects expire after 180 days; BigQuery Bronze is retained |
| Log retention | 30 days in the default bucket |
| Artifact cleanup | Keep the last 5 image tags |
| Review | Monthly billing review during the first three months |

---

## 8. What is not included

- Development time and opportunity cost.
- Taxes (ISS, IOF) and BRL/USD variation.
- Paid Looker Studio Pro features, if the optional manual report is used.
- A custom domain or hosting for a public web app.
- Support plans.
- Any future item-level ingestion or streaming architecture.

---

## 9. Conclusion

At the approved scope — one monthly snapshot, ~4,000 classifications per month, US multi-region — the expected operating cost is **under US$ 1 per month**. The dominant cost is the LLM, not the infrastructure.

The main financial risks are accidental full-coverage enrichment, unbounded retries, and queries without partition pruning. All three are addressed by explicit caps, cache, and BigQuery guardrails.

The estimate should be revisited after the first month of real usage, when token counts, retry rates, and query volumes can be measured instead of assumed.
