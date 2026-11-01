terraform {
  required_version = ">= 1.6"
}

variable "cloudflare_api_token" {
  type      = string
  sensitive = true
}
variable "zone_id" { type = string }
variable "account_id" { type = string }
variable "origin_ip" { type = string }

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}

module "cloudflare" {
  source     = "../../modules/cloudflare"
  zone_id    = var.zone_id
  account_id = var.account_id
  origin_ip  = var.origin_ip
  env        = "production"
}
