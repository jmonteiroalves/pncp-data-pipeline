variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "region" {
  description = "Region for the state bucket and workload identity."
  type        = string
  default     = "us-central1"
}

variable "state_bucket" {
  description = "Globally unique GCS bucket for Terraform state."
  type        = string
}

variable "github_repo" {
  description = "GitHub repository allowed to federate, as owner/repo."
  type        = string
}

variable "deploy_service_account" {
  description = "Account ID for the GitHub Actions deploy service account."
  type        = string
  default     = "sa-github-deploy"
}
