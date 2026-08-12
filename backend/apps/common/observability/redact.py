"""Redact secrets and credentials from logs."""

from __future__ import annotations

import re
from typing import Any

SENSITIVE_KEYS = frozenset(
    {
        "password",
        "password1",
        "password2",
        "passwd",
        "secret",
        "token",
        "access",
        "refresh",
        "access_token",
        "refresh_token",
        "authorization",
        "api_key",
        "apikey",
        "api-key",
        "credential",
        "credentials",
        "client_secret",
        "private_key",
        "jwt",
        "cookie",
        "csrftoken",
        "csrfmiddlewaretoken",
    }
)

_BEARER_RE = re.compile(r"(?i)(bearer\s+)[a-z0-9._\-]+")
_QUERY_SECRET_RE = re.compile(
    r"(?i)([?&](?:password|token|access|refresh|secret|api[_-]?key|authorization)=)[^&]*"
)


def is_sensitive_key(key: str) -> bool:
    normalized = key.strip().lower().replace("-", "_")
    if normalized in SENSITIVE_KEYS:
        return True
    return any(part in SENSITIVE_KEYS for part in normalized.split("_") if part)


def redact_mapping(data: dict[str, Any] | None) -> dict[str, Any]:
    if not data:
        return {}
    redacted: dict[str, Any] = {}
    for key, value in data.items():
        if is_sensitive_key(str(key)):
            redacted[key] = "[REDACTED]"
        elif isinstance(value, dict):
            redacted[key] = redact_mapping(value)
        else:
            redacted[key] = value
    return redacted


def scrub_message(message: str) -> str:
    cleaned = _BEARER_RE.sub(r"\1[REDACTED]", message)
    return _QUERY_SECRET_RE.sub(r"\1[REDACTED]", cleaned)
