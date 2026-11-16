terraform {
  required_version = ">= 1.13.0, < 2.0.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.14"
    }
  }
}

variable "storage_account_id" {
  description = "Resource ID of a dedicated storage account; do not use an account with unrelated lifecycle rules."
  type        = string
}

variable "repositories" {
  description = "Owner-approved repository keys mapped to private container names. This is storage provisioning, not an authorization allowlist."
  type        = map(string)
  validation {
    condition     = length(var.repositories) > 0 && length(distinct(values(var.repositories))) == length(var.repositories)
    error_message = "Provide at least one repository and a unique container per repository."
  }
  validation {
    condition     = alltrue([for name in values(var.repositories) : can(regex("^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$", name)) && !strcontains(name, "--")])
    error_message = "Container names must be 3–63 lowercase letters/numbers/hyphens, without consecutive or edge hyphens."
  }
}

variable "retention_days" {
  description = "Days after creation before blobs become eligible for lifecycle deletion; deletion is asynchronous."
  type        = number
  default     = 3
  validation {
    condition     = var.retention_days >= 1 && var.retention_days <= 30 && floor(var.retention_days) == var.retention_days
    error_message = "Retention must be an integer from 1 through 30 days."
  }
}

resource "azurerm_storage_container" "repository" {
  for_each              = var.repositories
  name                  = each.value
  storage_account_id    = var.storage_account_id
  container_access_type = "private"
  lifecycle {
    prevent_destroy = true
  }
}

resource "azurerm_storage_management_policy" "retention" {
  storage_account_id = var.storage_account_id
  rule {
    name    = "expire-ci-artifacts"
    enabled = true
    filters {
      prefix_match = [for container in azurerm_storage_container.repository : "${container.name}/"]
      blob_types   = ["blockBlob"]
    }
    actions {
      base_blob {
        delete_after_days_since_creation_greater_than = var.retention_days
      }
    }
  }
  lifecycle {
    prevent_destroy = true
  }
}

output "containers" {
  description = "Private container resource IDs by repository key."
  value       = { for repository, container in azurerm_storage_container.repository : repository => container.resource_manager_id }
}
