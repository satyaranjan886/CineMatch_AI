"""Production Celery tasks for recommendation pipelines.

All tasks are idempotent: repeated runs overwrite caches / upsert scores /
train a new artifact version. Retries use exponential backoff.
Distributed Redis locks prevent concurrent heavy jobs across workers.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.common.celery_utils import DEFAULT_TASK_KWARGS, HEAVY_TASK_KWARGS
from apps.common.locks import try_distributed_lock

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(name="recommendations.update_popularity_scores", **DEFAULT_TASK_KWARGS)
def update_popularity_scores(self) -> dict:
    from apps.recommendations.services.popularity import PopularityRecommendationService

    with try_distributed_lock("recommendations:popularity", timeout=900) as acquired:
        if not acquired:
            logger.info("popularity refresh skipped; lock held by another worker")
            return {
                "strategy": "popular",
                "skipped": True,
                "reason": "lock_held",
                "idempotent": True,
            }
        service = PopularityRecommendationService()
        count = service.refresh_cache()
    logger.info(
        "popularity scores refreshed", extra={"count": count, "retries": self.request.retries}
    )
    return {"strategy": "popular", "count": count, "idempotent": True}


@shared_task(name="recommendations.update_trending_scores", **DEFAULT_TASK_KWARGS)
def update_trending_scores(self) -> dict:
    from apps.recommendations.services.trending import TrendingRecommendationService

    with try_distributed_lock("recommendations:trending", timeout=600) as acquired:
        if not acquired:
            logger.info("trending refresh skipped; lock held by another worker")
            return {
                "strategy": "trending",
                "skipped": True,
                "reason": "lock_held",
                "idempotent": True,
            }
        service = TrendingRecommendationService()
        windows = getattr(settings, "RECOMMENDATION_TRENDING_WINDOWS_HOURS", [24, 168])
        results = {}
        for window_hours in windows:
            count = service.refresh_cache(context={"window_hours": window_hours})
            results[str(window_hours)] = count
    logger.info(
        "trending scores refreshed", extra={"windows": results, "retries": self.request.retries}
    )
    return {"strategy": "trending", "windows": results, "idempotent": True}


@shared_task(name="recommendations.train_collaborative_model", **HEAVY_TASK_KWARGS)
def train_collaborative_model(self) -> dict:
    from apps.recommendations.cache import invalidate_all_collaborative_caches
    from ml.collaborative.recommender import ActiveCollaborativeRecommender
    from ml.pipelines.collaborative import run_collaborative_training_pipeline

    lock_timeout = int(getattr(settings, "CF_TRAIN_LOCK_TIMEOUT_SECONDS", 3600))
    with try_distributed_lock("recommendations:cf_train", timeout=lock_timeout) as acquired:
        if not acquired:
            logger.info("collaborative training skipped; lock held by another worker")
            return {
                "strategy": "collaborative",
                "skipped": True,
                "reason": "lock_held",
                "idempotent": True,
            }
        report = run_collaborative_training_pipeline()
        ActiveCollaborativeRecommender.invalidate()
        invalidate_all_collaborative_caches()

    logger.info(
        "collaborative model trained",
        extra={"version": report.version, "retries": self.request.retries},
    )
    return {
        "strategy": "collaborative",
        "version": report.version,
        "model_name": report.model_name,
        "dataset_version": report.dataset_version,
        "artifact_location": report.artifact_location,
        "metrics": report.metrics,
        "user_count": report.user_count,
        "item_count": report.item_count,
        "interaction_count": report.interaction_count,
        "idempotent": True,
    }


@shared_task(name="recommendations.generate_home_recommendations", **DEFAULT_TASK_KWARGS)
def generate_home_recommendations(
    self, *, lookback_hours: int | None = None, limit: int | None = None
) -> dict:
    """
    Warm hybrid home caches for recently active users.

    Safe to re-run: overwrites Redis home entries for the current epoch/version.
    """
    from apps.interactions.models import MovieInteraction
    from apps.recommendations.services.hybrid import HybridHomeRecommendationService

    with try_distributed_lock("recommendations:home_precompute", timeout=1800) as acquired:
        if not acquired:
            return {
                "strategy": "home_precompute",
                "skipped": True,
                "reason": "lock_held",
                "idempotent": True,
            }

        lookback_hours = lookback_hours or getattr(settings, "HOME_PRECOMPUTE_LOOKBACK_HOURS", 24)
        limit = limit or getattr(settings, "HOME_PRECOMPUTE_USER_LIMIT", 200)
        since = timezone.now() - timedelta(hours=lookback_hours)

        user_ids = list(
            MovieInteraction.objects.filter(created_at__gte=since)
            .values_list("user_id", flat=True)
            .distinct()[:limit]
        )
        users = list(User.objects.filter(id__in=user_ids))
        service = HybridHomeRecommendationService()
        warmed = 0
        for user in users:
            service.get_home_recommendations(user=user)
            warmed += 1

    logger.info(
        "home recommendations precomputed",
        extra={"warmed": warmed, "lookback_hours": lookback_hours, "retries": self.request.retries},
    )
    return {"strategy": "home_precompute", "warmed": warmed, "idempotent": True}
