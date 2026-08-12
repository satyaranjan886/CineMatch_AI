variable "aws_region" {
  type        = string
  description = "Primary AWS region (multi-AZ within this region)."
  default     = "us-east-1"
}

variable "environment" {
  type        = string
  description = "Environment name (staging|production)."
  default     = "staging"
}

variable "project_name" {
  type    = string
  default = "cinematch"
}

variable "vpc_cidr" {
  type    = string
  default = "10.40.0.0/16"
}

variable "availability_zones" {
  type        = list(string)
  description = "At least two AZs for Multi-AZ data plane."
  default     = ["us-east-1a", "us-east-1b"]
}

variable "domain_name" {
  type        = string
  description = "Public DNS name (Route 53 + ACM). Leave empty to skip DNS/ACM wiring."
  default     = ""
}

variable "compute_mode" {
  type        = string
  description = "ecs (Fargate preferred) or asg (EC2 Auto Scaling + user data)."
  default     = "ecs"

  validation {
    condition     = contains(["ecs", "asg"], var.compute_mode)
    error_message = "compute_mode must be ecs or asg."
  }
}

variable "api_desired_count" {
  type        = number
  description = "Desired API tasks/instances across AZs."
  default     = 2
}

variable "celery_desired_count" {
  type        = number
  description = "Desired Celery worker tasks (beat stays at 1)."
  default     = 2
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.medium"
}

variable "redis_node_type" {
  type    = string
  default = "cache.t4g.micro"
}

variable "app_secrets_arn" {
  type        = string
  description = "Secrets Manager secret ARN holding JSON app secrets (never commit values)."
  default     = ""
}
