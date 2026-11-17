resource "google_storage_bucket" "lake" {
  name                        = var.bucket_name
  location                    = var.region
  force_destroy               = false
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age            = 180
      matches_prefix = ["bronze/"]
    }
  }

  depends_on = [google_project_service.enabled]
}

resource "google_storage_bucket_iam_member" "ingest_writer" {
  bucket = google_storage_bucket.lake.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.ingest.email}"
}
