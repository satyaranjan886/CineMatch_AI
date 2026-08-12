"""Personalized hybrid homepage recommendations."""

from __future__ import annotations

from typing import Any

from django.conf import settings

from apps.experiments.assignment import resolve_serving_decision
from apps.experiments.registry import build_ranking_service
from apps.recommendations.cache import (
    get_cached_home_recommendations,
    home_cache_key,
    set_cached_home_recommendations,
)
from ml.ranking.pipeline import HybridRecommendationPipeline
from ml.ranking.types import HomeRecommendationResult


class HybridHomeRecommendationService:
    cache_ttl = getattr(settings, "HYBRID_HOME_CACHE_TTL", 600)

    def __init__(self, *, pipeline: HybridRecommendationPipeline | None = None):
        self.pipeline = pipeline

    def get_home_recommendations(
        self,
        *,
        user,
        profile=None,
        context: dict[str, Any] | None = None,
    ) -> HomeRecommendationResult:
        context = context or {}
        profile = profile or user.get_primary_profile()
        profile_id = profile.id if profile is not None else "none"

        decision = resolve_serving_decision(user)
        version = decision.model_version
        experiment_context = {
            **context,
            "experiment_id": str(decision.experiment_id) if decision.experiment_id else None,
            "variant": decision.variant,
            "model_key": decision.model_key,
        }

        key = home_cache_key(
            user_id=user.id,
            profile_id=profile_id,
            version=version,
            context=experiment_context,
        )
        cached = get_cached_home_recommendations(key)
        if cached is not None:
            cached.context = {
                **cached.context,
                **{k: v for k, v in experiment_context.items() if v is not None},
            }
            return cached

        if self.pipeline is not None:
            pipeline = self.pipeline
        else:
            pipeline = HybridRecommendationPipeline(
                ranking_service=build_ranking_service(decision.model_key),
                model_version=version,
            )

        result = pipeline.build_home(user, context=experiment_context)
        set_cached_home_recommendations(key, result, self.cache_ttl)
        return HomeRecommendationResult(
            version=result.version,
            cached=False,
            sections=result.sections,
            context={
                **result.context,
                **{k: v for k, v in experiment_context.items() if v is not None},
            },
        )
