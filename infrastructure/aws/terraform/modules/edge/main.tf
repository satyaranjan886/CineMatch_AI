variable "project_name" { type = string }
variable "environment" { type = string }
variable "vpc_id" { type = string }
variable "public_subnet_ids" { type = list(string) }
variable "app_security_group_id" { type = string }
variable "domain_name" { type = string }
variable "health_check_path" { type = string }

locals {
  name         = "${var.project_name}-${var.environment}"
  create_dns   = var.domain_name != ""
}

resource "aws_security_group" "alb" {
  name   = "${local.name}-alb-edge"
  vpc_id = var.vpc_id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_lb" "api" {
  name               = "${local.name}-alb"
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = var.public_subnet_ids
}

resource "aws_lb_target_group" "api" {
  name        = "${local.name}-api"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    path                = var.health_check_path
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 15
    matcher             = "200"
  }
  deregistration_delay = 30
}

resource "aws_acm_certificate" "this" {
  count             = local.create_dns ? 1 : 0
  domain_name       = var.domain_name
  validation_method = "DNS"
}

resource "aws_lb_listener" "https" {
  count             = local.create_dns ? 1 : 0
  load_balancer_arn = aws_lb.api.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate.this[0].arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

resource "aws_lb_listener" "http_redirect" {
  load_balancer_arn = aws_lb.api.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

# Route 53 alias — create only when domain_name is set and a hosted zone exists.
data "aws_route53_zone" "this" {
  count = local.create_dns ? 1 : 0
  name  = var.domain_name
}

resource "aws_route53_record" "app" {
  count   = local.create_dns ? 1 : 0
  zone_id = data.aws_route53_zone.this[0].zone_id
  name    = var.domain_name
  type    = "A"
  alias {
    name                   = aws_lb.api.dns_name
    zone_id                = aws_lb.api.zone_id
    evaluate_target_health = true
  }
}

output "alb_dns_name" { value = aws_lb.api.dns_name }
output "api_target_group_arn" { value = aws_lb_target_group.api.arn }
output "alb_security_group_id" { value = aws_security_group.alb.id }
