"""Structured recommendation reason generation."""

from __future__ import annotations

from ml.ranking.filters import UserRecommendationContext
from ml.ranking.types import CandidateFeatures


def generate_reason(
    features: CandidateFeatures, *, user_context: UserRecommendationContext, movie
) -> str:
    sources = features.sources
    if not sources:
        return "Recommended for you"

    top_source = max(sources.items(), key=lambda item: item[1])[0]

    if top_source == "collaborative":
        if user_context.liked_titles:
            anchor = next(iter(user_context.liked_titles.values()))
            return f"Because you liked {anchor}"
        return "Recommended based on users with similar taste"

    if top_source == "recently_watched":
        if user_context.recent_watched_titles:
            anchor = next(iter(user_context.recent_watched_titles.values()))
            return f"Similar to movies you recently watched, including {anchor}"
        return "Similar to movies you recently watched"

    if top_source == "genre_preference" or features.genre_affinity >= 0.5:
        movie_genres = {link.genre.name for link in movie.movie_genres.all()}
        overlap = movie_genres & user_context.favorite_genre_names
        if overlap:
            genre = sorted(overlap)[0]
            return f"Matches your favorite genres, especially {genre}"
        return "Matches your favorite genres"

    if top_source == "trending":
        movie_genres = {link.genre.name for link in movie.movie_genres.all()}
        if movie_genres:
            return f"Trending in {sorted(movie_genres)[0]}"
        return "Trending now"

    if top_source == "popular":
        return "Top rated on CineMatch"

    if top_source == "semantic":
        return "Semantically similar to titles you enjoy"

    if top_source == "content":
        if user_context.liked_titles:
            anchor = next(iter(user_context.liked_titles.values()))
            return f"Because you liked {anchor}"
        return "Similar to movies in your taste profile"

    return "Recommended for you"
