output "bucket_name" {
  value = google_storage_bucket.lake.name
}

output "datasets" {
  value = [for dataset in google_bigquery_dataset.datasets : dataset.dataset_id]
}

output "artifact_repository" {
  value = google_artifact_registry_repository.pipeline.name
}

output "pipeline_image" {
  value = local.pipeline_image
}

output "dbt_image" {
  value = local.dbt_image
}

output "ingest_job" {
  value = google_cloud_run_v2_job.ingest.name
}

output "dbt_job" {
  value = google_cloud_run_v2_job.dbt.name
}

output "enrich_job" {
  value = google_cloud_run_v2_job.enrich.name
}

output "workflow" {
  value = google_workflows_workflow.pipeline.name
}

output "scheduler_job" {
  value = google_cloud_scheduler_job.daily.name
}

output "scheduler_service_account" {
  value = google_service_account.scheduler.email
}
