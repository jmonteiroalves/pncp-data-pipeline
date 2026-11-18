locals {
  alert_channels = var.alert_email == "" ? [] : [google_monitoring_notification_channel.email[0].id]
}

resource "google_monitoring_notification_channel" "email" {
  count = var.alert_email == "" ? 0 : 1

  project      = var.project_id
  display_name = "PNCP alerts"
  type         = "email"

  labels = {
    email_address = var.alert_email
  }
}

resource "google_logging_metric" "job_errors" {
  project     = var.project_id
  name        = "pncp_job_errors"
  description = "Error logs emitted by PNCP Cloud Run jobs"
  filter      = "resource.type=\"cloud_run_job\" AND severity>=ERROR"

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

resource "google_logging_metric" "ingest_429" {
  project     = var.project_id
  name        = "pncp_ingest_429"
  description = "PNCP API rate-limit retries"
  filter      = "resource.type=\"cloud_run_job\" AND jsonPayload.message=\"retrying PNCP request\" AND jsonPayload.reason=\"HTTP 429\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

resource "google_logging_metric" "llm_invalid" {
  project     = var.project_id
  name        = "pncp_llm_invalid"
  description = "Invalid structured responses from Gemini"
  filter      = "resource.type=\"cloud_run_job\" AND jsonPayload.message=\"invalid gemini response\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

resource "google_logging_metric" "snapshot_ingested" {
  project     = var.project_id
  name        = "pncp_snapshot_ingested"
  description = "Completed monthly snapshot days"
  filter      = "resource.type=\"cloud_run_job\" AND jsonPayload.message=\"day ingested\" AND jsonPayload.mode=\"snapshot\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

resource "google_monitoring_alert_policy" "job_errors" {
  project      = var.project_id
  display_name = "PNCP — job errors"
  combiner     = "OR"

  conditions {
    display_name = "Cloud Run job error logs"

    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/pncp_job_errors\" AND resource.type=\"cloud_run_job\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0

      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_COUNT"
        cross_series_reducer = "REDUCE_SUM"
        group_by_fields      = ["resource.label.job_name"]
      }
    }
  }

  notification_channels = local.alert_channels
  severity              = "ERROR"
}

resource "google_monitoring_alert_policy" "ingest_429" {
  project      = var.project_id
  display_name = "PNCP — 429 storm"
  combiner     = "OR"

  conditions {
    display_name = "More than 10 rate-limit retries in 15 minutes"

    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/pncp_ingest_429\" AND resource.type=\"cloud_run_job\""
      duration        = "900s"
      comparison      = "COMPARISON_GT"
      threshold_value = 10

      aggregations {
        alignment_period   = "900s"
        per_series_aligner = "ALIGN_COUNT"
      }
    }
  }

  notification_channels = local.alert_channels
  severity              = "WARNING"
}

resource "google_monitoring_alert_policy" "llm_invalid" {
  project      = var.project_id
  display_name = "PNCP — invalid LLM responses"
  combiner     = "OR"

  conditions {
    display_name = "Invalid structured responses in 30 minutes"

    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/pncp_llm_invalid\" AND resource.type=\"cloud_run_job\""
      duration        = "1800s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0

      aggregations {
        alignment_period   = "1800s"
        per_series_aligner = "ALIGN_COUNT"
      }
    }
  }

  notification_channels = local.alert_channels
  severity              = "WARNING"
}

resource "google_monitoring_dashboard" "operations" {
  project = var.project_id

  dashboard_json = jsonencode({
    displayName = "PNCP operations"

    mosaicLayout = {
      columns = 12

      tiles = [
        {
          width  = 6
          height = 4
          widget = {
            title = "Error logs"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"logging.googleapis.com/user/pncp_job_errors\""
                    aggregation = {
                      alignmentPeriod  = "300s"
                      perSeriesAligner = "ALIGN_RATE"
                    }
                  }
                }
              }]
              timeshiftDuration = "0s"
              yAxis             = { label = "errors/s", scale = "LINEAR" }
            }
          }
        },
        {
          xPos   = 6
          width  = 6
          height = 4
          widget = {
            title = "Rate-limit retries"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"logging.googleapis.com/user/pncp_ingest_429\""
                    aggregation = {
                      alignmentPeriod  = "900s"
                      perSeriesAligner = "ALIGN_RATE"
                    }
                  }
                }
              }]
              timeshiftDuration = "0s"
              yAxis             = { label = "retries/s", scale = "LINEAR" }
            }
          }
        },
        {
          yPos   = 4
          width  = 6
          height = 4
          widget = {
            title = "Invalid LLM responses"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"logging.googleapis.com/user/pncp_llm_invalid\""
                    aggregation = {
                      alignmentPeriod  = "1800s"
                      perSeriesAligner = "ALIGN_RATE"
                    }
                  }
                }
              }]
              timeshiftDuration = "0s"
              yAxis             = { label = "invalid/s", scale = "LINEAR" }
            }
          }
        },
        {
          xPos   = 6
          yPos   = 4
          width  = 6
          height = 4
          widget = {
            title = "Snapshot days"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"logging.googleapis.com/user/pncp_snapshot_ingested\""
                    aggregation = {
                      alignmentPeriod  = "3600s"
                      perSeriesAligner = "ALIGN_RATE"
                    }
                  }
                }
              }]
              timeshiftDuration = "0s"
              yAxis             = { label = "days", scale = "LINEAR" }
            }
          }
        }
      ]
    }
  })
}
