"""Hybrid recommendation pipeline orchestration."""

from __future__ import annotations

from django.conf import settings

from apps.movies.models import Movie
from ml.ranking.features import enrich_catalog_features
from ml.ranking.filters import build_user_context, filter_candidates
from ml.ranking.generators import generate_candidate_pool
from ml.ranking.pool import merge_candidates
from ml.ranking.ranker import RankingService, WeightedRankingModel
from ml.ranking.sections import (
    build_because_you_watched_section,
    build_continue_watching_section,
    build_favorite_genres_section,
    build_recommended_for_you_section,
    build_top_rated_section,
    build_trending_section,
)
from ml.ranking.types import HomeRecommendationResult


def _cold_start_weights() -> dict[str, float]:
    base = dict(getattr(settings, "RECOMMENDATION_WEIGHTS", {}))
    adjusted = {
        **base,
        "collaborative": base.get("collaborative", 0.3) * 0.15,
        "popularity": base.get("popularity", 0.1) * 1.8,
        "trending": base.get("trending", 0.1) * 1.5,
        "genre_preference": base.get("genre_preference", 0.15) * 1.2,
    }
    total = sum(adjusted.values()) or 1.0
    return {key: value / total for key, value in adjusted.items()}


def is_cold_start_user(user) -> bool:
    from ml.collaborative.recommender import ActiveCollaborativeRecommender

    recommender = ActiveCollaborativeRecommender()
    return recommender.user_interaction_count(user.id) < recommender.cold_start_threshold()


class HybridRecommendationPipeline:
    def __init__(
        self,
        ranking_service: RankingService | None = None,
        *,
        model_version: str | None = None,
    ):
        self.ranking_service = ranking_service
        self.model_version = model_version

    def build_home(self, user, *, context: dict | None = None) -> HomeRecommendationResult:
        import time

        context = context or {}
        timing_enabled = bool(getattr(settings, "LOADTEST_TIMING", False))
        t0 = time.perf_counter()
        user_context = build_user_context(user)
        t_ctx = time.perf_counter()

        candidates = generate_candidate_pool(user)
        t_gen = time.perf_counter()
        merged = merge_candidates(candidates)
        filtered = filter_candidates(merged, user_context=user_context, exclude_completed=True)
        enrich_catalog_features(filtered)
        t_feat = time.perf_counter()

        ranking_service = self.ranking_service
        # Cold-start users always get popularity/trending-heavy weights, even when an
        # experiment RankingService is injected for warm users.
        if is_cold_start_user(user):
            ranking_service = RankingService(WeightedRankingModel(weights=_cold_start_weights()))
        elif ranking_service is None:
            ranking_service = RankingService(WeightedRankingModel())

        ranked_pool = ranking_service.rank(filtered)
        t_rank = time.perf_counter()
        movies_by_id = {
            movie.id: movie
            for movie in Movie.objects.filter(
                id__in=[movie_id for movie_id, _, _ in ranked_pool]
            ).prefetch_related("movie_genres__genre")
        }
        t_db = time.perf_counter()

        version = self.model_version or getattr(settings, "RECOMMENDATION_VERSION", "v1")
        sections = [
            build_continue_watching_section(user),
            build_because_you_watched_section(user, user_context=user_context),
            build_recommended_for_you_section(
                user,
                ranked_pool=ranked_pool,
                movies_by_id=movies_by_id,
                user_context=user_context,
            ),
            build_trending_section(),
            build_top_rated_section(),
            build_favorite_genres_section(user, user_context=user_context),
        ]
        recommendation_count = sum(len(section.movies) for section in sections)
        t_end = time.perf_counter()

        result_context = {
            **context,
            "candidate_count": len(candidates),
            "merged_candidate_count": len(merged),
            "filtered_candidate_count": len(filtered),
            "recommendation_count": recommendation_count,
        }
        if timing_enabled:
            result_context["timings_ms"] = {
                "user_context_ms": round((t_ctx - t0) * 1000, 2),
                "candidate_generation_ms": round((t_gen - t_ctx) * 1000, 2),
                "feature_enrichment_ms": round((t_feat - t_gen) * 1000, 2),
                "ranking_ms": round((t_rank - t_feat) * 1000, 2),
                "database_ms": round((t_db - t_rank) * 1000, 2),
                "section_build_ms": round((t_end - t_db) * 1000, 2),
                "total_pipeline_ms": round((t_end - t0) * 1000, 2),
            }

        return HomeRecommendationResult(
            version=version,
            cached=False,
            sections=sections,
            context=result_context,
        )
