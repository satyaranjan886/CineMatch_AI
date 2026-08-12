"""Structured logging helpers."""

from __future__ import annotations

import json
import logging
from typing import Any

from apps.common.middleware import request_id_var
from apps.common.observability.context import endpoint_var, user_id_var
from apps.common.observability.redact import scrub_message

STRUCTURED_FIELDS = (
    "request_id",
    "user_id",
    "endpoint",
    "method",
    "status",
    "latency_ms",
    "error",
    "error_type",
    "event",
    "algorithm",
    "model_version",
    "cached",
    "candidate_count",
    "recommendation_count",
    "result_count",
    "cache",
    "task",
    "model",
)


class RequestContextFilter(logging.Filter):
    """Attach request-scoped fields onto every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = getattr(record, "request_id", None) or request_id_var.get()
        record.user_id = getattr(record, "user_id", None) or user_id_var.get()
        record.endpoint = getattr(record, "endpoint", None) or endpoint_var.get()
        return True


# Backwards-compatible alias used by settings.
RequestIDFilter = RequestContextFilter


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": scrub_message(record.getMessage()),
            "request_id": getattr(record, "request_id", "-"),
        }
        user_id = getattr(record, "user_id", None)
        if user_id and user_id != "-":
            payload["user_id"] = user_id
        endpoint = getattr(record, "endpoint", None)
        if endpoint and endpoint != "-":
            payload["endpoint"] = endpoint

        for field in STRUCTURED_FIELDS:
            if field in {"request_id", "user_id", "endpoint"}:
                continue
            value = getattr(record, field, None)
            if value is not None and value != "-":
                payload[field] = value

        if record.exc_info:
            payload["error"] = scrub_message(self.formatException(record.exc_info))
            payload["error_type"] = (
                record.exc_info[0].__name__ if record.exc_info[0] else "Exception"
            )
        return json.dumps(payload, default=str)
