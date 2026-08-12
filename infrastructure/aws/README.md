# AWS infrastructure (Terraform sketches)

Illustrative Terraform for a multi-AZ footprint (VPC, ALB, RDS, ElastiCache, S3, ECS notes).

## Important

- **Nothing here is applied automatically** by CI or agents.
- Do **not** run `terraform apply` unless an operator intentionally targets a
  real account with reviewed variables and secrets from Secrets Manager.
- These modules have **not** been validated against a live AWS account from this repo.

## Layout

```text
infrastructure/aws/
  README.md
  terraform/
    README.md
    versions.tf
    variables.tf
    outputs.tf
    main.tf
    terraform.tfvars.example   # no secrets
    modules/
      network/
      data/
      compute/
      edge/
```

## Secrets

Never put production passwords, JWT keys, or DB URLs in Terraform, Compose, GitHub, or source.
Wire runtime secrets from **AWS Secrets Manager** (or SSM SecureString).
