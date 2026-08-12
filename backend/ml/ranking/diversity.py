"""Diversity re-ranking for recommendation lists."""

from __future__ import annotations

from uuid import UUID

from django.conf import settings

from apps.movies.models import Movie
from ml.ranking.types import CandidateFeatures, RankedRecommendation


def _genre_set(movie: Movie) -> set[str]:
    return {link.genre.name for link in movie.movie_genres.all()}


def _genre_overlap(movie_a: Movie, movie_b: Movie) -> float:
    genres_a = _genre_set(movie_a)
    genres_b = _genre_set(movie_b)
    if not genres_a or not genres_b:
        return 0.0
    intersection = len(genres_a & genres_b)
    union = len(genres_a | genres_b)
    return intersection / union if union else 0.0


def rerank_with_diversity(
    ranked: list[tuple[UUID, float, CandidateFeatures, Movie, str]],
    *,
    limit: int,
    lambda_relevance: float | None = None,
) -> list[RankedRecommendation]:
    if not ranked:
        return []

    lambda_relevance = (
        lambda_relevance
        if lambda_relevance is not None
        else getattr(settings, "HYBRID_DIVERSITY_LAMBDA", 0.72)
    )

    selected: list[tuple[UUID, float, CandidateFeatures, Movie, str]] = []
    candidates = list(ranked)

    while candidates and len(selected) < limit:
        best_index = 0
        best_value = float("-inf")
        for index, item in enumerate(candidates):
            relevance = item[1]
            if not selected:
                diversity_penalty = 0.0
            else:
                diversity_penalty = max(_genre_overlap(item[3], chosen[3]) for chosen in selected)
            value = lambda_relevance * relevance - (1.0 - lambda_relevance) * diversity_penalty
            if value > best_value:
                best_value = value
                best_index = index
        selected.append(candidates.pop(best_index))

    return [
        RankedRecommendation(
            movie=item[3],
            score=item[1],
            reason=item[4],
            features=item[2],
            primary_source=max(item[2].sources, key=item[2].sources.get)
            if item[2].sources
            else "hybrid",
        )
        for item in selected
    ]
