resource "google_cloud_run_v2_job" "ingest" {
  project             = var.project_id
  location            = var.region
  name                = "pncp-ingest"
  deletion_protection = false

  template {
    template {
      service_account = google_service_account.ingest.email
      timeout         = "3600s"
      max_retries     = 1

      containers {
        image = local.pipeline_image
        args  = ["snapshot"]

        resources {
          limits = {
            cpu    = "1"
            memory = "1Gi"
          }
        }

        dynamic "env" {
          for_each = merge(local.common_env, {
            GCS_BUCKET                    = var.bucket_name
            GCS_PREFIX                    = "bronze/pncp"
            BRONZE_DATASET                = "bronze"
            CONTROL_DATASET               = "control"
            PNCP_MODALITIES               = "1,4,5,6,7,8,9,10,11,12"
            PNCP_REQUEST_INTERVAL_SECONDS = "1.25"
            PNCP_MAX_RETRIES              = "5"
          })
          content {
            name  = env.key
            value = env.value
          }
        }
      }
    }
  }

  depends_on = [
    google_artifact_registry_repository.pipeline,
    google_project_service.enabled,
  ]
}

resource "google_cloud_run_v2_job" "dbt" {
  project             = var.project_id
  location            = var.region
  name                = "pncp-dbt"
  deletion_protection = false

  template {
    template {
      service_account = google_service_account.dbt.email
      timeout         = "1800s"
      max_retries     = 1

      containers {
        image = local.dbt_image
        args  = ["build", "--project-dir", "dbt", "--profiles-dir", "dbt"]

        resources {
          limits = {
            cpu    = "1"
            memory = "1Gi"
          }
        }

        dynamic "env" {
          for_each = merge(local.common_env, {
            DBT_DATASET = "silver"
          })
          content {
            name  = env.key
            value = env.value
          }
        }
      }
    }
  }

  depends_on = [
    google_artifact_registry_repository.pipeline,
    google_project_service.enabled,
  ]
}

resource "google_cloud_run_v2_job" "enrich" {
  project             = var.project_id
  location            = var.region
  name                = "pncp-enrich"
  deletion_protection = false

  template {
    template {
      service_account = google_service_account.enrich.email
      timeout         = "3600s"
      max_retries     = 1

      containers {
        image = local.pipeline_image
        args  = ["enrich", "--limit", "5000", "--batch-size", "20"]

        resources {
          limits = {
            cpu    = "1"
            memory = "1Gi"
          }
        }

        dynamic "env" {
          for_each = merge(local.common_env, {
            SILVER_DATASET               = "silver"
            AI_DATASET                   = "ai"
            CONTROL_DATASET              = "control"
            VERTEX_LOCATION              = "global"
            LLM_MODEL                    = var.llm_model
            LLM_TEMPERATURE              = "0"
            LLM_SAMPLE_RATE              = tostring(var.llm_sample_rate)
            LLM_MONTHLY_CAP              = tostring(var.llm_monthly_cap)
            LLM_BATCH_SIZE               = "20"
            LLM_INPUT_PRICE_PER_MILLION  = "0.25"
            LLM_OUTPUT_PRICE_PER_MILLION = "1.50"
            LLM_PROMPT_VERSION           = "v1"
            LLM_TAXONOMY_VERSION         = "v1"
          })
          content {
            name  = env.key
            value = env.value
          }
        }
      }
    }
  }

  depends_on = [
    google_artifact_registry_repository.pipeline,
    google_project_service.enabled,
  ]
}
