"""Search / embedding Celery tasks."""

from __future__ import annotations

import logging

from celery import shared_task

from apps.common.celery_utils import HEAVY_TASK_KWARGS

logger = logging.getLogger(__name__)


@shared_task(name="search.generate_movie_embeddings", **HEAVY_TASK_KWARGS)
def generate_movie_embeddings(self, *, limit: int | None = None) -> dict:
    """
    Generate embeddings for released movies missing vectors.

    Idempotent: update_or_create per movie; re-running skips existing rows
    when only missing movies are selected.
    """
    from django.conf import settings

    from apps.common.locks import try_distributed_lock
    from apps.search.cache import invalidate_semantic_search_cache
    from apps.search.services.embeddings import MovieEmbeddingService

    lock_timeout = int(getattr(settings, "EMBEDDING_JOB_LOCK_TIMEOUT_SECONDS", 3600))
    with try_distributed_lock("search:embeddings", timeout=lock_timeout) as acquired:
        if not acquired:
            logger.info("embedding generation skipped; lock held by another worker")
            return {"skipped": True, "reason": "lock_held", "idempotent": True}

        service = MovieEmbeddingService()
        movies = service.movies_missing_embeddings()
        if limit is not None:
            movies = movies[:limit]

        result = service.generate_for_movies(movies)
        invalidate_semantic_search_cache()

    logger.info(
        "movie embeddings generated",
        extra={
            "created_count": result.created,
            "updated_count": result.updated,
            "skipped_count": result.skipped,
            "processed_count": result.processed,
            "task_retries": self.request.retries,
        },
    )
    return {
        "created": result.created,
        "updated": result.updated,
        "skipped": result.skipped,
        "processed": result.processed,
        "idempotent": True,
    }
