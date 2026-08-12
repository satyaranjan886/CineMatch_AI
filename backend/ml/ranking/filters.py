"""Candidate filtering for hybrid recommendations."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from django.utils import timezone

from apps.interactions.models import InteractionEventType, Like, MovieInteraction, WatchHistory
from apps.interactions.services.continue_watching import (
    CONTINUE_WATCHING_MAX_PERCENT,
    CONTINUE_WATCHING_MIN_PERCENT,
)
from apps.movies.models import Movie, MovieStatus
from ml.ranking.types import CandidateFeatures


@dataclass(frozen=True)
class UserRecommendationContext:
    user_id: UUID
    disliked_movie_ids: set[UUID]
    completed_movie_ids: set[UUID]
    continue_watching_movie_ids: set[UUID]
    interaction_strength: dict[UUID, float]
    liked_titles: dict[UUID, str]
    recent_watched_titles: dict[UUID, str]
    favorite_genre_names: set[str]


def build_user_context(user) -> UserRecommendationContext:
    from apps.accounts.models import UserPreference

    disliked = set(
        MovieInteraction.objects.filter(
            user=user, event_type=InteractionEventType.DISLIKE, movie_id__isnull=False
        ).values_list("movie_id", flat=True)
    )
    completed = set(
        WatchHistory.objects.filter(user=user, completed_at__isnull=False).values_list(
            "movie_id", flat=True
        )
    )
    completed.update(
        WatchHistory.objects.filter(user=user, watch_percentage__gte=95).values_list(
            "movie_id", flat=True
        )
    )

    continue_watching = set(
        WatchHistory.objects.filter(user=user)
        .filter(watch_percentage__gte=CONTINUE_WATCHING_MIN_PERCENT)
        .filter(watch_percentage__lte=CONTINUE_WATCHING_MAX_PERCENT)
        .filter(completed_at__isnull=True)
        .values_list("movie_id", flat=True)
    )

    liked_titles = {
        row.movie_id: row.movie.title
        for row in Like.objects.filter(user=user).select_related("movie")
    }
    recent_watched = {
        row.movie_id: row.movie.title
        for row in WatchHistory.objects.filter(user=user)
        .select_related("movie")
        .order_by("-last_watched_at")[:10]
    }

    interaction_strength: dict[UUID, float] = {}
    for movie_id in set(liked_titles) | set(recent_watched):
        interaction_strength[movie_id] = 1.0 if movie_id in liked_titles else 0.6

    preference = (
        UserPreference.objects.filter(user=user).prefetch_related("favorite_genres").first()
    )
    favorite_genres = set()
    if preference is not None:
        favorite_genres = {genre.name for genre in preference.favorite_genres.all()}

    return UserRecommendationContext(
        user_id=user.id,
        disliked_movie_ids=disliked,
        completed_movie_ids=completed,
        continue_watching_movie_ids=continue_watching,
        interaction_strength=interaction_strength,
        liked_titles=liked_titles,
        recent_watched_titles=recent_watched,
        favorite_genre_names=favorite_genres,
    )


def filter_candidates(
    features_by_movie: dict[UUID, CandidateFeatures],
    *,
    user_context: UserRecommendationContext,
    exclude_completed: bool = True,
) -> dict[UUID, CandidateFeatures]:
    if not features_by_movie:
        return {}

    movies = {
        movie.id: movie
        for movie in Movie.objects.filter(
            id__in=features_by_movie.keys(), status=MovieStatus.RELEASED
        ).prefetch_related("movie_genres__genre")
    }

    filtered: dict[UUID, CandidateFeatures] = {}
    today = timezone.now().date()

    for movie_id, features in features_by_movie.items():
        movie = movies.get(movie_id)
        if movie is None:
            continue
        if movie_id in user_context.disliked_movie_ids:
            continue
        if exclude_completed and movie_id in user_context.completed_movie_ids:
            continue

        features.interaction_strength = user_context.interaction_strength.get(movie_id, 0.0)
        features.rating_quality = min(max(movie.vote_average / 10.0, 0.0), 1.0)
        if movie.release_date:
            age_days = max((today - movie.release_date).days, 0)
            features.freshness_score = 1.0 / (1.0 + age_days / 365.0)
        else:
            features.freshness_score = 0.2

        if user_context.favorite_genre_names:
            movie_genres = {link.genre.name for link in movie.movie_genres.all()}
            overlap = len(movie_genres & user_context.favorite_genre_names)
            if overlap:
                features.genre_affinity = max(
                    features.genre_affinity, overlap / len(user_context.favorite_genre_names)
                )

        filtered[movie_id] = features

    return filtered
