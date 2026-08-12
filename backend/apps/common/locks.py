"""Distributed locks for multi-worker Celery safety."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@contextmanager
def try_distributed_lock(
    key: str,
    *,
    timeout: int = 3600,
    blocking: bool = False,
    blocking_timeout: float = 0.0,
) -> Iterator[bool]:
    """
    Acquire a Redis lock when available.

    Yields True when the lock is held (or when Redis locks are unavailable in
    local/test LocMem setups so single-process jobs still run). Yields False
    when another worker already holds the lock.
    """
    lock = None
    acquired = False
    try:
        from django_redis import get_redis_connection

        client = get_redis_connection("default")
        lock = client.lock(
            name=f"cinematch:lock:{key}",
            timeout=timeout,
            blocking_timeout=blocking_timeout if blocking else 0,
        )
        acquired = bool(lock.acquire(blocking=blocking))
    except Exception as exc:  # noqa: BLE001 — fall back for LocMem / misconfig
        logger.debug("distributed lock unavailable; proceeding without Redis lock: %s", exc)
        yield True
        return

    if not acquired:
        yield False
        return

    try:
        yield True
    finally:
        try:
            lock.release()
        except Exception:  # noqa: BLE001
            logger.warning("failed to release distributed lock %s", key, exc_info=True)
