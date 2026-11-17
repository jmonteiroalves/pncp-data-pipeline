locals {
  services = [
    "aiplatform.googleapis.com",
    "artifactregistry.googleapis.com",
    "bigquery.googleapis.com",
    "cloudscheduler.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "run.googleapis.com",
    "serviceusage.googleapis.com",
    "storage.googleapis.com",
    "workflows.googleapis.com",
  ]

  datasets = toset(["bronze", "silver", "gold", "ai", "control"])

  image_base     = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_repository}"
  pipeline_image = "${local.image_base}/pipeline:${var.image_tag}"
  dbt_image      = "${local.image_base}/dbt:${var.image_tag}"

  common_env = {
    GCP_PROJECT = var.project_id
    BQ_LOCATION = var.bq_location
    ENVIRONMENT = var.environment
    LOG_LEVEL   = "INFO"
  }
}

resource "google_project_service" "enabled" {
  for_each = toset(local.services)

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_service_account" "ingest" {
  project      = var.project_id
  account_id   = "sa-pncp-ingest"
  display_name = "PNCP ingest job"
}

resource "google_service_account" "dbt" {
  project      = var.project_id
  account_id   = "sa-pncp-dbt"
  display_name = "PNCP dbt job"
}

resource "google_service_account" "enrich" {
  project      = var.project_id
  account_id   = "sa-pncp-enrich"
  display_name = "PNCP enrichment job"
}

resource "google_service_account" "orchestrator" {
  project      = var.project_id
  account_id   = "sa-pncp-orchestrator"
  display_name = "PNCP workflow orchestrator"
}

resource "google_service_account" "scheduler" {
  project      = var.project_id
  account_id   = "sa-pncp-scheduler"
  display_name = "PNCP scheduler"
}

resource "google_project_iam_member" "job_user" {
  for_each = {
    ingest = google_service_account.ingest.email
    dbt    = google_service_account.dbt.email
    enrich = google_service_account.enrich.email
  }

  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${each.value}"
}

resource "google_project_iam_member" "orchestrator_run" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.orchestrator.email}"
}

resource "google_project_iam_member" "enrich_vertex" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.enrich.email}"
}

resource "google_artifact_registry_repository_iam_member" "readers" {
  for_each = {
    ingest = google_service_account.ingest.email
    dbt    = google_service_account.dbt.email
    enrich = google_service_account.enrich.email
  }

  project    = var.project_id
  location   = var.region
  repository = google_artifact_registry_repository.pipeline.name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${each.value}"
}
