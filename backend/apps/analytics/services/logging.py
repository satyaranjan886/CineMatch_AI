"""Recommendation serve logging."""

from __future__ import annotations

import logging
from uuid import UUID

from apps.analytics.models import RecommendationServeEvent

logger = logging.getLogger(__name__)


def log_recommendation_serve(
    *,
    algorithm: str,
    movie_ids: list[UUID | str],
    cached: bool = False,
    user=None,
    model_version: str = "",
    surface: str = "api",
    metadata: dict | None = None,
) -> RecommendationServeEvent | None:
    try:
        return RecommendationServeEvent.objects.create(
            user=user if getattr(user, "is_authenticated", False) else None,
            algorithm=algorithm,
            model_version=model_version or "",
            surface=surface,
            cached=bool(cached),
            item_count=len(movie_ids),
            movie_ids=[str(movie_id) for movie_id in movie_ids],
            metadata=metadata or {},
        )
    except Exception:
        # Never fail a recommendation response because analytics persistence failed.
        logger.exception("recommendation_serve_event_persist_failed")
        return None
