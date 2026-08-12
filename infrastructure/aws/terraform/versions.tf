terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Operators should configure a remote state backend (S3 + DynamoDB lock)
  # outside of git. Do not commit state files.
  # backend "s3" {}
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "cinematch"
      Environment = var.environment
      ManagedBy   = "terraform-manual"
    }
  }
}
