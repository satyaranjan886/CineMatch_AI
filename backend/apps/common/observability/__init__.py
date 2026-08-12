"""Production observability: structured logs, health, and Prometheus metrics."""

from apps.common.observability.metrics import (
    observe_cache,
    observe_celery_task,
    observe_inference,
    observe_recommendation,
    observe_search,
)
from apps.common.observability.redact import redact_mapping, scrub_message

__all__ = [
    "observe_cache",
    "observe_celery_task",
    "observe_inference",
    "observe_recommendation",
    "observe_search",
    "redact_mapping",
    "scrub_message",
]
