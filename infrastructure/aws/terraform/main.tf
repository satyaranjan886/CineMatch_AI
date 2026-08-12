# Illustrative composition — review and adapt before any apply.
# Secrets stay in Secrets Manager; only ARNs are referenced here.

module "network" {
  source = "./modules/network"

  project_name       = var.project_name
  environment        = var.environment
  vpc_cidr           = var.vpc_cidr
  availability_zones = var.availability_zones
}

module "data" {
  source = "./modules/data"

  project_name            = var.project_name
  environment             = var.environment
  vpc_id                  = module.network.vpc_id
  private_subnet_ids      = module.network.private_subnet_ids
  database_subnet_ids     = module.network.database_subnet_ids
  app_security_group_id   = module.network.app_security_group_id
  worker_security_group_id = module.network.worker_security_group_id
  db_instance_class       = var.db_instance_class
  redis_node_type         = var.redis_node_type
}

module "edge" {
  source = "./modules/edge"

  project_name          = var.project_name
  environment           = var.environment
  vpc_id                = module.network.vpc_id
  public_subnet_ids     = module.network.public_subnet_ids
  app_security_group_id = module.network.app_security_group_id
  domain_name           = var.domain_name
  health_check_path     = "/ready/"
}

module "compute" {
  source = "./modules/compute"

  project_name             = var.project_name
  environment              = var.environment
  compute_mode             = var.compute_mode
  vpc_id                   = module.network.vpc_id
  private_subnet_ids       = module.network.private_subnet_ids
  app_security_group_id    = module.network.app_security_group_id
  worker_security_group_id = module.network.worker_security_group_id
  target_group_arn         = module.edge.api_target_group_arn
  api_desired_count        = var.api_desired_count
  celery_desired_count     = var.celery_desired_count
  app_secrets_arn          = var.app_secrets_arn
  models_bucket_arn        = module.data.models_bucket_arn
  media_bucket_arn         = module.data.media_bucket_arn
  aws_region               = var.aws_region
}

output "vpc_id" {
  value = module.network.vpc_id
}

output "alb_dns_name" {
  value = module.edge.alb_dns_name
}

output "rds_endpoint" {
  value     = module.data.rds_endpoint
  sensitive = true
}

output "redis_endpoint" {
  value     = module.data.redis_endpoint
  sensitive = true
}

output "models_bucket" {
  value = module.data.models_bucket_name
}

output "media_bucket" {
  value = module.data.media_bucket_name
}
