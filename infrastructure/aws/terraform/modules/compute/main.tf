variable "project_name" { type = string }
variable "environment" { type = string }
variable "compute_mode" { type = string }
variable "vpc_id" { type = string }
variable "private_subnet_ids" { type = list(string) }
variable "app_security_group_id" { type = string }
variable "worker_security_group_id" { type = string }
variable "target_group_arn" { type = string }
variable "api_desired_count" { type = number }
variable "celery_desired_count" { type = number }
variable "app_secrets_arn" { type = string }
variable "models_bucket_arn" { type = string }
variable "media_bucket_arn" { type = string }
variable "aws_region" { type = string }

locals {
  name = "${var.project_name}-${var.environment}"
}

resource "aws_ecs_cluster" "this" {
  count = var.compute_mode == "ecs" ? 1 : 0
  name  = local.name
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/cinematch/${var.environment}/api"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/cinematch/${var.environment}/celery"
  retention_in_days = 30
}

resource "aws_iam_role" "task_execution" {
  name = "${local.name}-ecs-exec"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "task_execution" {
  role       = aws_iam_role.task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "task" {
  name = "${local.name}-ecs-task"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "task_data" {
  name = "${local.name}-task-data"
  role = aws_iam_role.task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
        Resource = [var.models_bucket_arn, "${var.models_bucket_arn}/*", var.media_bucket_arn, "${var.media_bucket_arn}/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = var.app_secrets_arn != "" ? [var.app_secrets_arn] : ["*"]
      }
    ]
  })
}

# Task definitions are environment-specific (image digests, secret keys).
# Operators register API, celery-worker, and celery-beat services separately:
# - API: desired_count = var.api_desired_count, attach to target_group_arn
# - Worker: desired_count = var.celery_desired_count, no load balancer
# - Beat: desired_count = 1 (never scale horizontally)

resource "aws_appautoscaling_target" "api" {
  count              = var.compute_mode == "ecs" ? 1 : 0
  max_capacity       = max(var.api_desired_count * 4, 4)
  min_capacity       = var.api_desired_count
  resource_id        = "service/${local.name}/${local.name}-api"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "api_cpu" {
  count              = var.compute_mode == "ecs" ? 1 : 0
  name               = "${local.name}-api-cpu"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.api[0].resource_id
  scalable_dimension = aws_appautoscaling_target.api[0].scalable_dimension
  service_namespace  = aws_appautoscaling_target.api[0].service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value = 60
  }
}

# Celery worker ASG / ECS scaling should track custom metrics:
# - Redis LLEN of the Celery queue
# - CloudWatch metric from a sidecar or AWS Distro for OpenTelemetry
# Example policy is omitted until the metric namespace is chosen.

output "ecs_cluster_name" {
  value = try(aws_ecs_cluster.this[0].name, null)
}

output "task_role_arn" {
  value = aws_iam_role.task.arn
}

output "notes" {
  value = <<-EOT
    Register three ECS services (or ASG launch templates) manually after images exist:
    1) api  — ALB target group ${var.target_group_arn}, count ${var.api_desired_count}
    2) celery-worker — count ${var.celery_desired_count}, no public ports
    3) celery-beat — count 1
    Inject secrets from ${var.app_secrets_arn} via task definition secrets blocks.
    Set CF_ARTIFACT_URI_PREFIX=s3://<models-bucket>/cf and CF_ARTIFACT_SYNC_ENABLED=true.
  EOT
}
