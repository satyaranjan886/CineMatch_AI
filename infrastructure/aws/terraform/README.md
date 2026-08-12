# Terraform — CineMatch multi-AZ (manual apply only)

Illustrative root module wiring VPC, ALB, ECS (or ASG), RDS Multi-AZ,
ElastiCache Redis, S3, IAM, Secrets Manager references, Route 53, and ACM.

```bash
# Operator-driven only — never automate against unknown accounts from this repo.
cd infrastructure/aws/terraform
cp terraform.tfvars.example terraform.tfvars   # fill non-secret values
terraform init
terraform plan                                 # review carefully
# terraform apply                              # only after human approval
```

This repository’s CI **must not** run `terraform apply`.
