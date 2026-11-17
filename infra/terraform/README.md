# Terraform

Infrastructure as code is implemented in phase 6 of the roadmap.

Planned modules:

| Module | Resources |
|---|---|
| `bootstrap` | State bucket and Workload Identity Federation |
| `iam` | Service accounts and least-privilege roles |
| `storage` | GCS lake bucket, lifecycle and IAM |
| `bigquery` | Datasets, tables and partitioning |
| `artifact_registry` | Container repository and cleanup policy |
| `cloud_run` | Ingest, dbt and enrichment jobs |
| `orchestration` | Scheduler and Workflows |
| `observability` | Log-based metrics, alerts and budget |

See [architecture.md](../../docs/architecture.md) and
[roadmap.md](../../docs/roadmap.md).
