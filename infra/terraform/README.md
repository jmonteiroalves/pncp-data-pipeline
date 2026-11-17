# Terraform

Provisions the PNCP pipeline on Google Cloud.

## Layout

| Path | Purpose |
|---|---|
| `bootstrap/` | State bucket, Workload Identity Federation, deploy service account |
| `versions.tf` | Provider and GCS backend |
| `main.tf` | APIs, service accounts, project-level IAM |
| `storage.tf` | Lake bucket and lifecycle |
| `bigquery.tf` | Datasets and dataset-level IAM |
| `artifact_registry.tf` | Docker repository |
| `cloud_run.tf` | Ingest, dbt, and enrichment jobs |
| `orchestration.tf` | Workflow and Cloud Scheduler |
| `../workflows/pipeline.yaml` | Workflow definition |

## Bootstrap

Run once, from a machine with owner access. It uses local state.

```bash
terraform -chdir=infra/terraform/bootstrap init
terraform -chdir=infra/terraform/bootstrap apply \
  -var="project_id=pncp-pipeline-dev" \
  -var="state_bucket=pncp-pipeline-dev-tfstate" \
  -var="github_repo=jmonteiroalves/pncp-data-pipeline"
```

Outputs:

- state bucket
- deploy service account
- Workload Identity Provider

## Main stack

```bash
terraform -chdir=infra/terraform init \
  -backend-config="bucket=pncp-pipeline-dev-tfstate" \
  -backend-config="prefix=terraform/state"

terraform -chdir=infra/terraform plan \
  -var="project_id=pncp-pipeline-dev" \
  -var="region=us-central1" \
  -var="image_tag=<git-sha>"

terraform -chdir=infra/terraform apply \
  -var="project_id=pncp-pipeline-dev" \
  -var="region=us-central1" \
  -var="image_tag=<git-sha>"
```

The lake bucket and the five BigQuery datasets were created before Terraform
adoption and are imported into state:

```bash
terraform import google_storage_bucket.lake pncp-pipeline-dev-lake
terraform import 'google_bigquery_dataset.datasets["bronze"]' projects/pncp-pipeline-dev/datasets/bronze
# ... silver, gold, ai, control
```

A fresh project does not need the imports; the same configuration creates them.

## Cloud Run jobs

Images must exist before the jobs are created. The deploy workflow builds and
pushes both images before `terraform apply`:

- `pipeline:<sha>` — ingest and enrichment
- `dbt:<sha>` — dbt build

## CI/CD

`.github/workflows/deploy.yml` authenticates through Workload Identity
Federation, builds and pushes the images, then runs `terraform plan` and
`terraform apply` with `image_tag=$GITHUB_SHA`.

`.github/workflows/terraform-plan.yml` runs `terraform fmt` and `plan` on pull
requests that touch `infra/`.

Repository variables required:

| Variable | Value |
|---|---|
| `GCP_PROJECT` | `pncp-pipeline-dev` |
| `GCP_REGION` | `us-central1` |
| `WIF_PROVIDER` | provider resource name from bootstrap |
| `DEPLOY_SA` | deploy service account email |
| `TF_STATE_BUCKET` | `pncp-pipeline-dev-tfstate` |
| `ARTIFACT_REPOSITORY` | `pncp-pipeline` |

## Rollback

Images are immutable tags. Roll back a job by applying the previous tag:

```bash
terraform -chdir=infra/terraform apply \
  -var="project_id=pncp-pipeline-dev" \
  -var="region=us-central1" \
  -var="image_tag=<previous-git-sha>"
```

Or, for a quick operational rollback:

```bash
gcloud run jobs update pncp-ingest \
  --region us-central1 \
  --image us-central1-docker.pkg.dev/pncp-pipeline-dev/pncp-pipeline/pipeline:<previous-sha>
```

Re-run the deploy workflow afterwards so Terraform reconciles the tag back to
`main`. A Git revert is the preferred path because it keeps state and code aligned.

## Budget

The US$ 10-equivalent budget (R$ 50) was created in the billing console before
Terraform adoption and remains the account-level guardrail. Billing budgets are
not managed by the project deploy service account.
