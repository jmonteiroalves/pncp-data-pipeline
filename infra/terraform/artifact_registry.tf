resource "google_artifact_registry_repository" "pipeline" {
  project       = var.project_id
  location      = var.region
  repository_id = var.artifact_repository
  format        = "DOCKER"
  description   = "PNCP pipeline images (ingest, dbt, enrich)"

  depends_on = [google_project_service.enabled]
}
