"""Trending recommendation service."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.utils import timezone

from apps.interactions.models import MovieInteraction
from apps.movies.models import Movie, MovieStatus
from apps.recommendations.base import BaseRecommendationService, RecommendationItem
from apps.recommendations.models import MovieTrendingScore
from apps.recommendations.scoring.trending import TrendingEvent, trending_score


class TrendingRecommendationService(BaseRecommendationService):
    strategy_name = "trending"
    cache_key = "trending"
    cache_ttl = getattr(settings, "RECOMMENDATION_TRENDING_CACHE_TTL", 300)

    def compute_scores(self, *, context: dict[str, Any] | None = None) -> list[RecommendationItem]:
        context = context or {}
        window_hours = int(
            context.get("window_hours", settings.RECOMMENDATION_TRENDING_DEFAULT_WINDOW_HOURS)
        )
        half_life = float(
            context.get("half_life_hours", settings.RECOMMENDATION_TRENDING_HALF_LIFE_HOURS)
        )
        now = timezone.now()
        since = now - timezone.timedelta(hours=window_hours)

        interaction_rows = list(
            MovieInteraction.objects.filter(
                created_at__gte=since,
                movie_id__isnull=False,
            ).values_list("movie_id", "event_type", "created_at", "user_id")
        )
        if not interaction_rows:
            from django.db import connection, transaction

            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT pg_advisory_xact_lock(%s)",
                        [0xC11E0000 + int(window_hours)],
                    )
                MovieTrendingScore.objects.filter(window_hours=window_hours).delete()
            return []

        movie_ids = {row[0] for row in interaction_rows}
        movies = {
            movie.id: movie
            for movie in Movie.objects.filter(
                id__in=movie_ids, status=MovieStatus.RELEASED
            ).prefetch_related("movie_genres__genre")
        }

        events_by_movie: dict = {}
        for movie_id, event_type, created_at, user_id in interaction_rows:
            movie = movies.get(movie_id)
            if movie is None:
                continue
            events_by_movie.setdefault(movie_id, {"movie": movie, "events": []})
            events_by_movie[movie_id]["events"].append(
                TrendingEvent(
                    event_type=event_type,
                    created_at=created_at,
                    user_id=str(user_id),
                )
            )

        scored: list[RecommendationItem] = []
        bulk_rows: list[MovieTrendingScore] = []

        for payload in events_by_movie.values():
            movie = payload["movie"]
            score, unique_users = trending_score(
                payload["events"],
                half_life_hours=half_life,
                now=now,
            )
            if score <= 0:
                continue
            scored.append(
                RecommendationItem(
                    movie=movie,
                    score=score,
                    reason=f"Trending in the last {window_hours} hours",
                )
            )
            bulk_rows.append(
                MovieTrendingScore(
                    movie=movie,
                    window_hours=window_hours,
                    score=score,
                    unique_users=unique_users,
                    computed_at=now,
                )
            )

        scored.sort(key=lambda item: item.score, reverse=True)

        from django.db import connection, transaction

        # Atomic replace + transaction-scoped advisory lock so concurrent workers
        # cannot interleave delete/insert against the unique (movie, window) key.
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(%s)",
                    [0xC11E0000 + int(window_hours)],
                )
            MovieTrendingScore.objects.filter(window_hours=window_hours).delete()
            if bulk_rows:
                MovieTrendingScore.objects.bulk_create(bulk_rows)

        return scored
