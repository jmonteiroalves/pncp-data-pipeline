# Operations runbook

## Signals

| Signal | Where | Meaning |
|---|---|---|
| `PNCP — job errors` | Cloud Monitoring email | Any `ERROR` log from a Cloud Run job |
| `PNCP — 429 storm` | Cloud Monitoring email | More than 10 rate-limit retries in 15 minutes |
| `PNCP — invalid LLM responses` | Cloud Monitoring email | Gemini returned unparseable or misaligned JSON |
| Budget alert | Cloud Billing | 50%, 90%, or 100% of the R$ 50 monthly budget |
| Operations dashboard | Cloud Monitoring → Dashboards → PNCP operations | Error, 429, invalid LLM, and snapshot volume |

## First checks

```bash
PROJECT=pncp-pipeline-dev
gcloud config set project "$PROJECT"

gcloud workflows executions list pncp-daily-pipeline \
  --location us-central1 --limit 5 \
  --format='table(name,state,startTime,endTime)'

gcloud run jobs executions list --job pncp-ingest \
  --region us-central1 --limit 5 \
  --format='table(name,status.startTime,status.completionTime)'
```

To read a failed execution:

```bash
gcloud run jobs executions describe <execution> \
  --region us-central1 --format='value(status.conditions)'

gcloud logging read \
  'resource.type="cloud_run_job" AND resource.labels.job_name="pncp-ingest"' \
  --limit 50 --format='value(timestamp,severity,jsonPayload.message)'
```

## Monthly snapshot missed

The pipeline runs on day 8 and processes the first Tuesday of the month. If the
job fails, the job-error alert fires. Re-run the snapshot manually:

```bash
python -m pncp_pipeline snapshot --date YYYY-MM-DD --force
```

The Gold models only accept dates with a successful `snapshot` run, so a
failed snapshot does not leak partial data into the dashboard.

## 429 storm

1. Do not add workers; the PNCP rate limit gets worse with concurrency.
2. Check the retry delays and page numbers in the logs.
3. Let the current job finish if it is still retrying.
4. If the job failed, re-run the same Cloud Run job; checkpoints skip completed days.
5. Split the next backfill into 3-day chunks and run it off-peak.

```bash
gcloud run jobs execute pncp-ingest --region us-central1 --wait
```

## Job failure

- `pncp-ingest`: re-run. The checkpoint table prevents duplicate work.
- `pncp-dbt`: fix the model or test, then re-run. Gold is rebuilt from Silver.
- `pncp-enrich`: cached descriptions are skipped; failed rows are stored with
  `validation_status = 'failed'` and retried on the next run.

```bash
gcloud run jobs execute pncp-dbt --region us-central1 --wait
```

## Partial load or schema drift

1. The raw payload is in GCS; no data is lost.
2. Quarantine rows in `silver.quarantine_*` show structural failures.
3. Update the extractor or dbt model.
4. Replay the affected window with the backfill command, or load local Bronze
   with `scripts/load_local_bronze.py`.

## Invalid LLM responses

1. Check `control.llm_requests` for the failing `request_id` and error.
2. Re-run enrichment; the repair prompt is attempted twice per batch.
3. If the model changed behaviour, pin the previous model or prompt version.
4. Failed rows remain in `ai.classificacao` with `validation_status = 'failed'`
   and are excluded from Gold.

## Budget exhaustion

1. Pause the scheduler.
2. Keep dbt running so the published data stays consistent.
3. Inspect `control.llm_requests` by model and day.
4. Reduce `llm_monthly_cap`, lower the sample rate, or temporarily disable the
   enrich job in the workflow.
5. Resume after the next billing cycle or after raising the budget.

```bash
gcloud scheduler jobs pause pncp-daily --location us-central1
gcloud scheduler jobs resume pncp-daily --location us-central1
```

## Rollback

Roll back a job image with Terraform so state and code stay aligned:

```bash
terraform -chdir=infra/terraform apply \
  -var="project_id=pncp-pipeline-dev" \
  -var="region=us-central1" \
  -var="image_tag=<previous-git-sha>"
```

For an emergency, update the job directly and reconcile with Terraform
afterwards.

## Dashboard refresh

The public dashboard is static. After a pipeline run:

```bash
python scripts/export_dashboard.py
git add docs/dashboard/data.json
git commit -m "data: refresh dashboard"
git push
```

GitHub Pages rebuilds automatically.

## Alert simulation

The log-based metrics accept real job logs only. To validate the error policy,
run a job with an intentionally invalid argument and confirm the execution
failure appears in the operations dashboard. Alert delivery depends on the
notification channel configured in Terraform (`alert_email`).

## Known limits

- The demo uses monthly one-day snapshots; Gold keeps only the current calendar
  year, while the local Bronze retains seven days from the earlier backfill.
- Budget alerts are configured in the billing console, not by the deploy
  service account.
- The dashboard export is manual; a scheduled refresh can be added to GitHub
  Actions.
