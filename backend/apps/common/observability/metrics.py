"""Prometheus metrics and domain observation helpers."""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager

from django.conf import settings
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
    multiprocess,
)

logger = logging.getLogger("cinematch.observability")

_REGISTRY: CollectorRegistry | None = None

HTTP_REQUESTS = None
HTTP_LATENCY = None
HTTP_ERRORS = None
RECOMMENDATION_REQUESTS = None
RECOMMENDATION_LATENCY = None
RECOMMENDATION_CANDIDATES = None
RECOMMENDATION_RESULTS = None
CACHE_HITS = None
CACHE_MISSES = None
CELERY_TASKS = None
CELERY_LATENCY = None
INFERENCE_REQUESTS = None
INFERENCE_LATENCY = None
SEARCH_REQUESTS = None
SEARCH_LATENCY = None


def _metrics_enabled() -> bool:
    return bool(getattr(settings, "METRICS_ENABLED", True))


def get_registry() -> CollectorRegistry:
    global _REGISTRY
    if _REGISTRY is not None:
        return _REGISTRY

    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        _REGISTRY = registry
    else:
        from prometheus_client import REGISTRY

        _REGISTRY = REGISTRY
    return _REGISTRY


def _init_metrics() -> None:
    global HTTP_REQUESTS, HTTP_LATENCY, HTTP_ERRORS
    global RECOMMENDATION_REQUESTS, RECOMMENDATION_LATENCY
    global RECOMMENDATION_CANDIDATES, RECOMMENDATION_RESULTS
    global CACHE_HITS, CACHE_MISSES
    global CELERY_TASKS, CELERY_LATENCY
    global INFERENCE_REQUESTS, INFERENCE_LATENCY
    global SEARCH_REQUESTS, SEARCH_LATENCY

    if HTTP_REQUESTS is not None:
        return

    registry = get_registry()
    # Avoid double-registration under the default REGISTRY when imported twice.
    if not os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        existing = getattr(registry, "_names_to_collectors", {})
    else:
        existing = {}

    def _counter(name: str, documentation: str, labelnames: list[str]) -> Counter:
        if name in existing:
            return existing[name]  # type: ignore[return-value]
        return Counter(name, documentation, labelnames, registry=registry)

    def _histogram(name: str, documentation: str, labelnames: list[str], buckets=None) -> Histogram:
        if name in existing:
            return existing[name]  # type: ignore[return-value]
        kwargs = {"registry": registry}
        if buckets is not None:
            kwargs["buckets"] = buckets
        return Histogram(name, documentation, labelnames, **kwargs)

    HTTP_REQUESTS = _counter(
        "cinematch_http_requests_total",
        "Total HTTP requests",
        ["method", "endpoint", "status"],
    )
    HTTP_LATENCY = _histogram(
        "cinematch_http_request_duration_seconds",
        "HTTP request latency in seconds",
        ["method", "endpoint"],
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
    )
    HTTP_ERRORS = _counter(
        "cinematch_http_errors_total",
        "HTTP responses with status >= 400",
        ["method", "endpoint", "status"],
    )
    RECOMMENDATION_REQUESTS = _counter(
        "cinematch_recommendation_requests_total",
        "Recommendation serve requests",
        ["algorithm", "cached", "model_version"],
    )
    RECOMMENDATION_LATENCY = _histogram(
        "cinematch_recommendation_duration_seconds",
        "Recommendation serve latency in seconds",
        ["algorithm"],
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
    )
    RECOMMENDATION_CANDIDATES = _histogram(
        "cinematch_recommendation_candidate_count",
        "Candidate pool size before final ranking",
        ["algorithm"],
        buckets=(0, 1, 5, 10, 25, 50, 100, 250, 500, 1000),
    )
    RECOMMENDATION_RESULTS = _histogram(
        "cinematch_recommendation_result_count",
        "Final recommendation item count",
        ["algorithm"],
        buckets=(0, 1, 5, 10, 20, 40, 60, 100),
    )
    CACHE_HITS = _counter(
        "cinematch_cache_hits_total",
        "Cache hits",
        ["cache"],
    )
    CACHE_MISSES = _counter(
        "cinematch_cache_misses_total",
        "Cache misses",
        ["cache"],
    )
    CELERY_TASKS = _counter(
        "cinematch_celery_tasks_total",
        "Celery task outcomes",
        ["task", "status"],
    )
    CELERY_LATENCY = _histogram(
        "cinematch_celery_task_duration_seconds",
        "Celery task runtime in seconds",
        ["task"],
        buckets=(0.01, 0.05, 0.1, 0.5, 1, 5, 15, 60, 300, 900, 1800),
    )
    INFERENCE_REQUESTS = _counter(
        "cinematch_model_inference_total",
        "Model inference calls",
        ["model", "status"],
    )
    INFERENCE_LATENCY = _histogram(
        "cinematch_model_inference_duration_seconds",
        "Model inference latency in seconds",
        ["model"],
        buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
    )
    SEARCH_REQUESTS = _counter(
        "cinematch_search_requests_total",
        "Semantic search requests",
        ["cached"],
    )
    SEARCH_LATENCY = _histogram(
        "cinematch_search_duration_seconds",
        "Semantic search latency in seconds",
        [],
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
    )


def ensure_metrics() -> None:
    if _metrics_enabled():
        _init_metrics()


def render_metrics() -> tuple[bytes, str]:
    ensure_metrics()
    return generate_latest(get_registry()), CONTENT_TYPE_LATEST


def observe_http(*, method: str, endpoint: str, status: int, latency_seconds: float) -> None:
    if not _metrics_enabled():
        return
    ensure_metrics()
    status_label = str(status)
    HTTP_REQUESTS.labels(method=method, endpoint=endpoint, status=status_label).inc()
    HTTP_LATENCY.labels(method=method, endpoint=endpoint).observe(latency_seconds)
    if status >= 400:
        HTTP_ERRORS.labels(method=method, endpoint=endpoint, status=status_label).inc()


def observe_cache(*, cache_name: str, hit: bool) -> None:
    if not _metrics_enabled():
        return
    ensure_metrics()
    if hit:
        CACHE_HITS.labels(cache=cache_name).inc()
    else:
        CACHE_MISSES.labels(cache=cache_name).inc()


def observe_recommendation(
    *,
    algorithm: str,
    model_version: str = "",
    latency_seconds: float,
    candidate_count: int | None = None,
    recommendation_count: int,
    cached: bool,
    user_id: str | None = None,
) -> None:
    """Record recommendation metrics and a privacy-safe structured log line."""
    version = model_version or "unknown"
    if _metrics_enabled():
        ensure_metrics()
        RECOMMENDATION_REQUESTS.labels(
            algorithm=algorithm,
            cached=str(bool(cached)).lower(),
            model_version=version,
        ).inc()
        RECOMMENDATION_LATENCY.labels(algorithm=algorithm).observe(latency_seconds)
        RECOMMENDATION_RESULTS.labels(algorithm=algorithm).observe(recommendation_count)
        if candidate_count is not None:
            RECOMMENDATION_CANDIDATES.labels(algorithm=algorithm).observe(candidate_count)

    logger.info(
        "recommendation_serve",
        extra={
            "event": "recommendation_serve",
            "algorithm": algorithm,
            "model_version": version,
            "latency_ms": round(latency_seconds * 1000, 2),
            "candidate_count": candidate_count if candidate_count is not None else "-",
            "recommendation_count": recommendation_count,
            "cached": cached,
            "user_id": user_id or "-",
        },
    )


def observe_search(*, cached: bool, latency_seconds: float, result_count: int) -> None:
    if _metrics_enabled():
        ensure_metrics()
        SEARCH_REQUESTS.labels(cached=str(bool(cached)).lower()).inc()
        SEARCH_LATENCY.observe(latency_seconds)

    logger.info(
        "search_request",
        extra={
            "event": "search_request",
            "cached": cached,
            "latency_ms": round(latency_seconds * 1000, 2),
            "result_count": result_count,
        },
    )


def observe_celery_task(
    *,
    task_name: str,
    status: str,
    latency_seconds: float | None = None,
) -> None:
    if not _metrics_enabled():
        return
    ensure_metrics()
    CELERY_TASKS.labels(task=task_name, status=status).inc()
    if latency_seconds is not None:
        CELERY_LATENCY.labels(task=task_name).observe(latency_seconds)


@contextmanager
def observe_inference(*, model: str) -> Iterator[None]:
    started = time.perf_counter()
    status = "ok"
    try:
        yield
    except Exception:
        status = "error"
        raise
    finally:
        elapsed = time.perf_counter() - started
        if _metrics_enabled():
            ensure_metrics()
            INFERENCE_REQUESTS.labels(model=model, status=status).inc()
            INFERENCE_LATENCY.labels(model=model).observe(elapsed)
        logger.debug(
            "model_inference",
            extra={
                "event": "model_inference",
                "model": model,
                "status": status,
                "latency_ms": round(elapsed * 1000, 2),
            },
        )
