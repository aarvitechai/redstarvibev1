terraform {
  required_providers {
    cloudflare = { source = "cloudflare/cloudflare", version = "~> 4.0" }
  }
}

variable "zone_id" { type = string }
variable "account_id" { type = string }
variable "origin_ip" { type = string }
variable "env" { type = string }
variable "prefix" {
  type        = string
  description = "Subdomain prefix: empty for production, for example staging. for staging"
  default     = ""
}

locals {
  names = toset(["${var.prefix}@", "${var.prefix}www", "${var.prefix}api", "${var.prefix}ws", "${var.prefix}mcp"])
}

resource "cloudflare_record" "app" {
  for_each = local.names
  zone_id  = var.zone_id
  name     = each.value
  type     = "A"
  content  = var.origin_ip
  proxied  = true
}

resource "cloudflare_r2_bucket" "raw" {
  account_id = var.account_id
  name       = "rsv-raw-${var.env}"
}

resource "cloudflare_r2_bucket" "public" {
  account_id = var.account_id
  name       = "rsv-public-${var.env}"
}
