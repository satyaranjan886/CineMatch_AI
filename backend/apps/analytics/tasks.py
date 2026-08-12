"""Analytics Celery tasks."""

from __future__ import annotations

import logging

from celery import shared_task

from apps.common.celery_utils import DEFAULT_TASK_KWARGS

logger = logging.getLogger(__name__)


@shared_task(name="analytics.compute_daily_snapshot", **DEFAULT_TASK_KWARGS)
def compute_daily_snapshot_task(self):
    """Upsert today's analytics snapshot. Safe to run repeatedly."""
    from apps.analytics.services.aggregation import compute_daily_snapshot

    snapshot = compute_daily_snapshot()
    logger.info(
        "analytics daily snapshot computed",
        extra={"date": snapshot.date.isoformat(), "retries": self.request.retries},
    )
    return {
        "date": snapshot.date.isoformat(),
        "computed_at": snapshot.computed_at.isoformat(),
        "idempotent": True,
    }
