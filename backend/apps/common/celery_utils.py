"""Shared Celery task defaults for production-quality background jobs."""

from __future__ import annotations

from typing import Any

# Safe defaults: late ack + retries with exponential backoff.
# Tasks that call these must remain idempotent (upsert / overwrite / epoch bump).
DEFAULT_TASK_KWARGS: dict[str, Any] = {
    "bind": True,
    "autoretry_for": (Exception,),
    "retry_backoff": True,
    "retry_backoff_max": 600,
    "retry_jitter": True,
    "max_retries": 3,
    "acks_late": True,
    "reject_on_worker_lost": True,
}

HEAVY_TASK_KWARGS: dict[str, Any] = {
    **DEFAULT_TASK_KWARGS,
    "max_retries": 2,
    "soft_time_limit": 1800,
    "time_limit": 2100,
}
