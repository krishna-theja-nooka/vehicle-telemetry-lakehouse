terraform {
  required_version = ">= 1.7, < 2.0"
  required_providers {
    google = { source = "hashicorp/google", version = "~> 6.0" }
  }
}
variable "project_id" { type = string }
variable "region" {
  type    = string
  default = "us-central1"
}
variable "bucket_name" {
  type        = string
  description = "Globally unique name for the synthetic telemetry bucket"
}
provider "google" {
  project = var.project_id
  region  = var.region
}
resource "google_storage_bucket" "telemetry" {
  name                        = var.bucket_name
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
  versioning { enabled = true }
  lifecycle_rule {
    condition { age = 30 }
    action { type = "Delete" }
  }
}
resource "google_bigquery_dataset" "fleet" {
  dataset_id                 = "synthetic_fleet"
  location                   = var.region
  delete_contents_on_destroy = false
  default_table_expiration_ms = 2592000000
}
output "bucket" { value = google_storage_bucket.telemetry.name }
output "dataset" { value = google_bigquery_dataset.fleet.dataset_id }
