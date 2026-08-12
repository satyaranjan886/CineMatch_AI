"""Popularity-based recommendation service."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db.models import Avg, Count, Max
from django.utils import timezone

from apps.interactions.models import (
    InteractionEventType,
    Like,
    MovieInteraction,
    Rating,
    WatchHistory,
)
from apps.movies.models import Movie, MovieStatus
from apps.recommendations.base import BaseRecommendationService, RecommendationItem
from apps.recommendations.models import MoviePopularityScore
from apps.recommendations.scoring.popularity import PopularitySignals, popularity_score

VIEW_EVENTS = {
    InteractionEventType.IMPRESSION,
    InteractionEventType.CLICK,
    InteractionEventType.OPEN,
    InteractionEventType.PLAY,
    InteractionEventType.WATCH_START,
}


class PopularityRecommendationService(BaseRecommendationService):
    strategy_name = "popular"
    cache_key = "popular"
    cache_ttl = getattr(settings, "RECOMMENDATION_POPULAR_CACHE_TTL", 900)

    def compute_scores(self, *, context: dict[str, Any] | None = None) -> list[RecommendationItem]:
        global_average = Rating.objects.aggregate(avg=Avg("score"))["avg"] or 7.0
        minimum_votes = getattr(settings, "RECOMMENDATION_MIN_VOTES_PRIOR", 10.0)
        now = timezone.now()

        movies = list(
            Movie.objects.filter(status=MovieStatus.RELEASED).prefetch_related(
                "movie_genres__genre"
            )
        )
        if not movies:
            return []

        movie_ids = [movie.id for movie in movies]

        views_map = dict(
            MovieInteraction.objects.filter(movie_id__in=movie_ids, event_type__in=VIEW_EVENTS)
            .values("movie_id")
            .annotate(total=Count("id"))
            .values_list("movie_id", "total")
        )
        unique_users_map = dict(
            MovieInteraction.objects.filter(movie_id__in=movie_ids)
            .values("movie_id")
            .annotate(total=Count("user_id", distinct=True))
            .values_list("movie_id", "total")
        )
        completions_map = dict(
            MovieInteraction.objects.filter(
                movie_id__in=movie_ids,
                event_type=InteractionEventType.WATCH_COMPLETE,
            )
            .values("movie_id")
            .annotate(total=Count("id"))
            .values_list("movie_id", "total")
        )
        likes_map = dict(
            Like.objects.filter(movie_id__in=movie_ids)
            .values("movie_id")
            .annotate(total=Count("id"))
            .values_list("movie_id", "total")
        )
        ratings_stats = {
            row["movie_id"]: row
            for row in Rating.objects.filter(movie_id__in=movie_ids)
            .values("movie_id")
            .annotate(count=Count("id"), avg=Avg("score"))
        }
        last_event_map = dict(
            MovieInteraction.objects.filter(movie_id__in=movie_ids)
            .values("movie_id")
            .annotate(last=Max("created_at"))
            .values_list("movie_id", "last")
        )
        completed_history_map = dict(
            WatchHistory.objects.filter(movie_id__in=movie_ids, completed_at__isnull=False)
            .values("movie_id")
            .annotate(total=Count("id"))
            .values_list("movie_id", "total")
        )

        scored: list[RecommendationItem] = []
        bulk_scores: list[MoviePopularityScore] = []

        for movie in movies:
            mid = movie.id
            rating_row = ratings_stats.get(mid, {})
            rating_count = rating_row.get("count", 0) or 0
            average_rating = float(rating_row.get("avg") or movie.vote_average or global_average)

            last_event = last_event_map.get(mid)
            days_since = None
            if last_event is not None:
                days_since = (now - last_event).total_seconds() / 86400.0

            signals = PopularitySignals(
                views=views_map.get(mid, 0),
                unique_users=unique_users_map.get(mid, 0),
                completions=completions_map.get(mid, 0) + completed_history_map.get(mid, 0),
                likes=likes_map.get(mid, 0),
                rating_count=rating_count,
                average_rating=average_rating,
                catalog_popularity=movie.popularity,
                catalog_vote_average=movie.vote_average,
                days_since_last_event=days_since,
            )
            score = popularity_score(
                signals,
                minimum_votes=minimum_votes,
                global_average=float(global_average),
            )

            reason = "Popular with strong engagement across views, users, and ratings"
            if signals.unique_users < minimum_votes:
                reason = "Popular title with growing engagement"

            scored.append(RecommendationItem(movie=movie, score=score, reason=reason))
            bulk_scores.append(
                MoviePopularityScore(
                    movie=movie,
                    score=score,
                    signals={
                        "views": signals.views,
                        "unique_users": signals.unique_users,
                        "completions": signals.completions,
                        "likes": signals.likes,
                        "rating_count": signals.rating_count,
                        "average_rating": signals.average_rating,
                    },
                    computed_at=now,
                )
            )

        scored.sort(key=lambda item: item.score, reverse=True)

        from django.db import transaction

        with transaction.atomic():
            MoviePopularityScore.objects.filter(movie_id__in=movie_ids).delete()
            MoviePopularityScore.objects.bulk_create(bulk_scores)

        return scored
