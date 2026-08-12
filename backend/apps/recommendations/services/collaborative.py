"""Personalized collaborative filtering recommendations."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from django.conf import settings

from apps.movies.models import Movie, MovieStatus
from apps.recommendations.base import RecommendationItem, RecommendationResult
from apps.recommendations.cache import get_cached_recommendations, set_cached_recommendations
from apps.recommendations.services.popularity import PopularityRecommendationService
from ml.collaborative.recommender import ActiveCollaborativeRecommender


class CollaborativeRecommendationService:
    strategy_name = "collaborative"
    cache_key = "collaborative"
    cache_ttl = getattr(settings, "RECOMMENDATION_COLLABORATIVE_CACHE_TTL", 600)

    def __init__(self, *, recommender: ActiveCollaborativeRecommender | None = None):
        self.recommender = recommender or ActiveCollaborativeRecommender()

    def get_recommendations(
        self,
        *,
        user,
        limit: int = 20,
        context: dict[str, Any] | None = None,
    ) -> RecommendationResult:
        context = context or {}
        if user is None or not getattr(user, "is_authenticated", False):
            return RecommendationResult(strategy=self.strategy_name, items=[], context=context)

        if self._is_cold_start(user):
            fallback = PopularityRecommendationService().get_recommendations(limit=limit)
            return RecommendationResult(
                strategy="popular_fallback",
                items=fallback.items[:limit],
                cached=fallback.cached,
                context={**context, "fallback": True, "reason": "insufficient_interactions"},
            )

        cache_extra = str(user.id)
        cached_items = get_cached_recommendations(self.cache_key, cache_extra)
        if cached_items is not None:
            return RecommendationResult(
                strategy=self.strategy_name,
                items=cached_items[:limit],
                cached=True,
                context=context,
            )

        items = self.compute_scores(user=user, context=context)
        set_cached_recommendations(self.cache_key, cache_extra, items, self.cache_ttl)
        return RecommendationResult(
            strategy=self.strategy_name,
            items=items[:limit],
            cached=False,
            context=context,
        )

    def compute_scores(
        self,
        *,
        user,
        context: dict[str, Any] | None = None,
    ) -> list[RecommendationItem]:
        exclude_ids = self._seen_movie_ids(user)
        recommendations = self.recommender.recommend_for_user(
            user.id,
            limit=50,
            exclude_movie_ids=exclude_ids,
        )
        if not recommendations:
            return []

        movie_ids = [rec.movie_id for rec in recommendations]
        movies = Movie.objects.filter(
            id__in=movie_ids,
            status=MovieStatus.RELEASED,
        ).prefetch_related("movie_genres__genre")
        movie_map = {movie.id: movie for movie in movies}

        items: list[RecommendationItem] = []
        seen: set[UUID] = set()
        for recommendation in recommendations:
            if recommendation.movie_id in seen:
                continue
            movie = movie_map.get(recommendation.movie_id)
            if movie is None:
                continue
            seen.add(recommendation.movie_id)
            items.append(
                RecommendationItem(
                    movie=movie,
                    score=recommendation.score,
                    reason="Recommended from users with similar tastes",
                )
            )
        return items

    def _is_cold_start(self, user) -> bool:
        threshold = self.recommender.cold_start_threshold()
        return self.recommender.user_interaction_count(user.id) < threshold

    def _seen_movie_ids(self, user) -> set[UUID]:
        from apps.interactions.models import Like, Rating, WatchHistory, Watchlist

        seen = set(Like.objects.filter(user=user).values_list("movie_id", flat=True))
        seen.update(Rating.objects.filter(user=user).values_list("movie_id", flat=True))
        seen.update(WatchHistory.objects.filter(user=user).values_list("movie_id", flat=True))
        seen.update(Watchlist.objects.filter(user=user).values_list("movie_id", flat=True))
        return seen
