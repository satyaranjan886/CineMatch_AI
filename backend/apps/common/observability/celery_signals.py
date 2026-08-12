"""Celery signal hooks for task metrics."""

from __future__ import annotations

import time

from celery.signals import task_failure, task_postrun, task_prerun

from apps.common.observability.metrics import observe_celery_task

_TASK_START: dict[str, float] = {}


def connect_celery_signals() -> None:
    task_prerun.connect(_on_task_prerun, weak=False)
    task_postrun.connect(_on_task_postrun, weak=False)
    task_failure.connect(_on_task_failure, weak=False)


def _task_key(task_id: str | None, task_name: str) -> str:
    return f"{task_name}:{task_id or '-'}"


def _on_task_prerun(sender=None, task_id=None, task=None, **kwargs):
    name = getattr(task, "name", None) or getattr(sender, "name", "unknown")
    _TASK_START[_task_key(task_id, name)] = time.perf_counter()


def _on_task_postrun(sender=None, task_id=None, task=None, state=None, **kwargs):
    name = getattr(task, "name", None) or getattr(sender, "name", "unknown")
    key = _task_key(task_id, name)
    started = _TASK_START.pop(key, None)
    latency = time.perf_counter() - started if started is not None else None
    status = (state or "SUCCESS").lower()
    if status == "success":
        status = "success"
    observe_celery_task(task_name=name, status=status, latency_seconds=latency)


def _on_task_failure(sender=None, task_id=None, exception=None, **kwargs):
    name = getattr(sender, "name", "unknown")
    key = _task_key(task_id, name)
    started = _TASK_START.pop(key, None)
    latency = time.perf_counter() - started if started is not None else None
    observe_celery_task(task_name=name, status="failure", latency_seconds=latency)
