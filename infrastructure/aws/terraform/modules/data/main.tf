variable "project_name" { type = string }
variable "environment" { type = string }
variable "vpc_id" { type = string }
variable "private_subnet_ids" { type = list(string) }
variable "database_subnet_ids" { type = list(string) }
variable "app_security_group_id" { type = string }
variable "worker_security_group_id" { type = string }
variable "db_instance_class" { type = string }
variable "redis_node_type" { type = string }

locals {
  name = "${var.project_name}-${var.environment}"
}

# Passwords must come from Secrets Manager at apply time (data source), never git.
data "aws_secretsmanager_secret_version" "db_master" {
  # Operator creates this secret before apply.
  secret_id = "${local.name}/rds/master"
}

locals {
  db_secret = jsondecode(data.aws_secretsmanager_secret_version.db_master.secret_string)
}

resource "aws_db_subnet_group" "this" {
  name       = "${local.name}-db"
  subnet_ids = var.database_subnet_ids
}

resource "aws_security_group" "database" {
  name   = "${local.name}-rds"
  vpc_id = var.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [var.app_security_group_id, var.worker_security_group_id]
  }
}

resource "aws_db_instance" "postgres" {
  identifier                 = "${local.name}-postgres"
  engine                     = "postgres"
  engine_version             = "16"
  instance_class             = var.db_instance_class
  allocated_storage          = 100
  max_allocated_storage      = 500
  storage_encrypted          = true
  multi_az                   = true
  db_subnet_group_name       = aws_db_subnet_group.this.name
  vpc_security_group_ids     = [aws_security_group.database.id]
  db_name                    = "cinematch"
  username                   = local.db_secret["username"]
  password                   = local.db_secret["password"]
  backup_retention_period    = 7
  deletion_protection        = true
  skip_final_snapshot        = false
  final_snapshot_identifier  = "${local.name}-final"
  performance_insights_enabled = true
  # Install pgvector via custom parameter group / extension after bootstrap.
  # Do NOT run production Postgres in Docker on EC2.
}

resource "aws_elasticache_subnet_group" "this" {
  name       = "${local.name}-redis"
  subnet_ids = var.private_subnet_ids
}

resource "aws_security_group" "redis" {
  name   = "${local.name}-elasticache"
  vpc_id = var.vpc_id

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [var.app_security_group_id, var.worker_security_group_id]
  }
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id       = "${local.name}-redis"
  description                = "CineMatch cache + Celery broker"
  engine                     = "redis"
  engine_version             = "7.1"
  node_type                  = var.redis_node_type
  num_cache_clusters         = 2
  automatic_failover_enabled = true
  multi_az_enabled           = true
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  subnet_group_name          = aws_elasticache_subnet_group.this.name
  security_group_ids         = [aws_security_group.redis.id]
  # AUTH token from Secrets Manager — set auth_token via operator pipeline.
}

resource "aws_s3_bucket" "models" {
  bucket = "${local.name}-models"
}

resource "aws_s3_bucket_versioning" "models" {
  bucket = aws_s3_bucket.models.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "models" {
  bucket = aws_s3_bucket.models.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "models" {
  bucket                  = aws_s3_bucket.models.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket" "media" {
  bucket = "${local.name}-media"
}

resource "aws_s3_bucket_versioning" "media" {
  bucket = aws_s3_bucket.media.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_public_access_block" "media" {
  bucket                  = aws_s3_bucket.media.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

output "rds_endpoint" { value = aws_db_instance.postgres.address }
output "redis_endpoint" { value = aws_elasticache_replication_group.redis.primary_endpoint_address }
output "models_bucket_name" { value = aws_s3_bucket.models.bucket }
output "models_bucket_arn" { value = aws_s3_bucket.models.arn }
output "media_bucket_name" { value = aws_s3_bucket.media.bucket }
output "media_bucket_arn" { value = aws_s3_bucket.media.arn }
