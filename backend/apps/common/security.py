"""Shared security helpers for production hardening."""

from __future__ import annotations

import ipaddress

from django.conf import settings
from django.http import HttpRequest


def client_ip(request: HttpRequest) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return (request.META.get("REMOTE_ADDR") or "").strip()


def is_private_or_loopback_ip(ip: str) -> bool:
    if not ip:
        return False
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return bool(address.is_private or address.is_loopback or address.is_link_local)


def metrics_request_authorized(request: HttpRequest) -> bool:
    """Authorize Prometheus scrapes via bearer token and/or private networks."""
    if not getattr(settings, "METRICS_ENABLED", True):
        return False

    token = (getattr(settings, "METRICS_SCRAPE_TOKEN", "") or "").strip()
    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    header_token = request.META.get("HTTP_X_METRICS_TOKEN", "")
    token_ok = False
    if token:
        token_ok = auth_header == f"Bearer {token}" or header_token == token

    allow_private = bool(getattr(settings, "METRICS_ALLOW_PRIVATE_NETWORK", True))
    private_ok = allow_private and is_private_or_loopback_ip(client_ip(request))

    require_token = bool(getattr(settings, "METRICS_REQUIRE_TOKEN", False))
    if require_token:
        return token_ok
    if token:
        # Token configured: accept token or private network (Prometheus on Docker/VPC).
        return token_ok or private_ok
    # No token: private/loopback only outside DEBUG.
    if getattr(settings, "DEBUG", False):
        return True
    return private_ok


def csrf_origins_are_https(origins: list[str]) -> bool:
    return all(origin.startswith("https://") for origin in origins if origin)


def cors_origins_are_https(origins: list[str]) -> bool:
    return all(origin.startswith("https://") for origin in origins if origin)
