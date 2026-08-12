"""Feature enrichment for ranked candidates."""

from __future__ import annotations

from uuid import UUID

from django.conf import settings

from apps.recommendations.models import MoviePopularityScore, MovieTrendingScore
from ml.ranking.types import CandidateFeatures


def enrich_catalog_features(features_by_movie: dict[UUID, CandidateFeatures]) -> None:
    if not features_by_movie:
        return

    movie_ids = list(features_by_movie.keys())
    popularity = {
        row.movie_id: row.score
        for row in MoviePopularityScore.objects.filter(movie_id__in=movie_ids)
    }
    window = getattr(settings, "RECOMMENDATION_TRENDING_DEFAULT_WINDOW_HOURS", 24)
    trending = {
        row.movie_id: row.score
        for row in MovieTrendingScore.objects.filter(movie_id__in=movie_ids, window_hours=window)
    }

    max_popularity = max(popularity.values(), default=0.0) or 1.0
    max_trending = max(trending.values(), default=0.0) or 1.0

    for movie_id, features in features_by_movie.items():
        if features.popularity_score <= 0.0 and movie_id in popularity:
            features.popularity_score = popularity[movie_id] / max_popularity
        if features.trending_score <= 0.0 and movie_id in trending:
            features.trending_score = trending[movie_id] / max_trending
