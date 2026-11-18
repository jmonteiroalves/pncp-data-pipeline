variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "region" {
  description = "Region for Cloud Run, Artifact Registry, Workflows, and the lake bucket."
  type        = string
  default     = "us-central1"
}

variable "bq_location" {
  description = "BigQuery dataset location."
  type        = string
  default     = "US"
}

variable "github_repo" {
  description = "GitHub repository allowed to deploy, as owner/repo."
  type        = string
  default     = "jmonteiroalves/pncp-data-pipeline"
}

variable "bucket_name" {
  description = "Cloud Storage lake bucket."
  type        = string
  default     = "pncp-pipeline-dev-lake"
}

variable "artifact_repository" {
  description = "Artifact Registry Docker repository ID."
  type        = string
  default     = "pncp-pipeline"
}

variable "image_tag" {
  description = "Image tag deployed to Cloud Run Jobs."
  type        = string
  default     = "latest"
}

variable "environment" {
  description = "Environment label."
  type        = string
  default     = "dev"
}

variable "llm_model" {
  description = "Gemini model used by the enrichment job."
  type        = string
  default     = "gemini-3.1-flash-lite"
}

variable "llm_sample_rate" {
  description = "Deterministic sampling rate for enrichment."
  type        = number
  default     = 0.1
}

variable "llm_monthly_cap" {
  description = "Maximum unique descriptions enriched per month."
  type        = number
  default     = 10000
}

variable "scheduler_timezone" {
  description = "Timezone for the daily scheduler."
  type        = string
  default     = "America/Sao_Paulo"
}

variable "alert_email" {
  description = "Optional email for Cloud Monitoring alerts."
  type        = string
  default     = ""
}

variable "scheduler_cron" {
  description = "Cron expression for the monthly snapshot (day 8)."
  type        = string
  default     = "0 3 8 * *"
}
