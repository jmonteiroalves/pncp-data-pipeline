resource "google_workflows_workflow" "pipeline" {
  project         = var.project_id
  region          = var.region
  name            = "pncp-daily-pipeline"
  description     = "PNCP ingest, dbt, enrichment, and Gold refresh"
  service_account = google_service_account.orchestrator.email
  source_contents = file("${path.module}/../workflows/pipeline.yaml")

  user_env_vars = {
    PROJECT_ID = var.project_id
    REGION     = var.region
  }

  depends_on = [google_project_service.enabled]
}

resource "google_project_iam_member" "scheduler_workflows" {
  project = var.project_id
  role    = "roles/workflows.invoker"
  member  = "serviceAccount:${google_service_account.scheduler.email}"
}

resource "google_cloud_scheduler_job" "daily" {
  project     = var.project_id
  region      = var.region
  name        = "pncp-daily"
  description = "Daily PNCP pipeline"
  schedule    = var.scheduler_cron
  time_zone   = var.scheduler_timezone

  http_target {
    http_method = "POST"
    uri         = "https://workflowexecutions.googleapis.com/v1/projects/${var.project_id}/locations/${var.region}/workflows/${google_workflows_workflow.pipeline.name}/executions"
    body        = base64encode("{}")
    headers = {
      "Content-Type" = "application/json"
    }

    oauth_token {
      service_account_email = google_service_account.scheduler.email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }

  attempt_deadline = "320s"

  depends_on = [
    google_project_service.enabled,
    google_project_iam_member.scheduler_workflows,
  ]
}
