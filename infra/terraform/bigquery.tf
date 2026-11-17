resource "google_bigquery_dataset" "datasets" {
  for_each = local.datasets

  project                    = var.project_id
  dataset_id                 = each.value
  location                   = var.bq_location
  friendly_name              = "PNCP ${each.value}"
  description                = "PNCP pipeline ${each.value} layer"
  delete_contents_on_destroy = false

  depends_on = [google_project_service.enabled]
}

locals {
  dataset_bindings = {
    ingest_bronze = {
      dataset = "bronze"
      role    = "roles/bigquery.dataEditor"
      member  = google_service_account.ingest.email
    }
    ingest_control = {
      dataset = "control"
      role    = "roles/bigquery.dataEditor"
      member  = google_service_account.ingest.email
    }
    dbt_bronze = {
      dataset = "bronze"
      role    = "roles/bigquery.dataViewer"
      member  = google_service_account.dbt.email
    }
    dbt_silver = {
      dataset = "silver"
      role    = "roles/bigquery.dataEditor"
      member  = google_service_account.dbt.email
    }
    dbt_gold = {
      dataset = "gold"
      role    = "roles/bigquery.dataEditor"
      member  = google_service_account.dbt.email
    }
    dbt_ai = {
      dataset = "ai"
      role    = "roles/bigquery.dataViewer"
      member  = google_service_account.dbt.email
    }
    enrich_silver = {
      dataset = "silver"
      role    = "roles/bigquery.dataViewer"
      member  = google_service_account.enrich.email
    }
    enrich_ai = {
      dataset = "ai"
      role    = "roles/bigquery.dataEditor"
      member  = google_service_account.enrich.email
    }
    enrich_control = {
      dataset = "control"
      role    = "roles/bigquery.dataEditor"
      member  = google_service_account.enrich.email
    }
  }
}

resource "google_bigquery_dataset_iam_member" "bindings" {
  for_each = local.dataset_bindings

  project    = var.project_id
  dataset_id = google_bigquery_dataset.datasets[each.value.dataset].dataset_id
  role       = each.value.role
  member     = "serviceAccount:${each.value.member}"
}
