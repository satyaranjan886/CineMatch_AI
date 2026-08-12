"""Load timestamped interactions for offline evaluation."""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from django.conf import settings
from django.utils import timezone

from apps.interactions.models import (
    InteractionEventType,
    Like,
    MovieInteraction,
    Rating,
    WatchHistory,
    Watchlist,
)
from apps.movies.models import MovieStatus
from ml.evaluation.types import TimedInteraction

POSITIVE_EVENT_TYPES = {
    InteractionEventType.WATCH_COMPLETE,
    InteractionEventType.WATCH_PROGRESS,
    InteractionEventType.WATCHLIST_ADD,
    InteractionEventType.LIKE,
    InteractionEventType.RATING,
}


class TimedInteractionLoader:
    """Load positive user-movie interactions with event timestamps."""

    DEFAULT_WEIGHTS = {
        "watch_complete": 5.0,
        "like": 4.0,
        "rating": 3.0,
        "watch_progress": 2.0,
        "watchlist_add": 1.5,
    }

    def __init__(self, *, weights: dict[str, float] | None = None):
        self.weights = weights or getattr(settings, "CF_INTERACTION_WEIGHTS", self.DEFAULT_WEIGHTS)

    def load(self) -> list[TimedInteraction]:
        raw: list[TimedInteraction] = []
        raw.extend(self._load_movie_interactions())
        raw.extend(self._load_likes())
        raw.extend(self._load_ratings())
        raw.extend(self._load_watch_history())
        raw.extend(self._load_watchlist())
        return self._aggregate_by_user_movie(raw)

    def _aggregate_by_user_movie(
        self, interactions: list[TimedInteraction]
    ) -> list[TimedInteraction]:
        grouped: dict[tuple[UUID, UUID], TimedInteraction] = {}
        for interaction in interactions:
            key = (interaction.user_id, interaction.movie_id)
            existing = grouped.get(key)
            if existing is None:
                grouped[key] = interaction
                continue
            grouped[key] = TimedInteraction(
                user_id=interaction.user_id,
                movie_id=interaction.movie_id,
                weight=max(existing.weight, interaction.weight),
                timestamp=max(existing.timestamp, interaction.timestamp),
                source=interaction.source
                if interaction.weight >= existing.weight
                else existing.source,
            )
        return sorted(
            grouped.values(),
            key=lambda item: (str(item.user_id), item.timestamp, str(item.movie_id)),
        )

    def _load_movie_interactions(self) -> list[TimedInteraction]:
        event_map = {
            InteractionEventType.WATCH_COMPLETE: "watch_complete",
            InteractionEventType.WATCH_PROGRESS: "watch_progress",
            InteractionEventType.WATCHLIST_ADD: "watchlist_add",
            InteractionEventType.LIKE: "like",
            InteractionEventType.RATING: "rating",
        }
        rows = MovieInteraction.objects.filter(
            movie_id__isnull=False,
            movie__status=MovieStatus.RELEASED,
            event_type__in=event_map,
        ).only("user_id", "movie_id", "event_type", "watch_percentage", "created_at")

        interactions: list[TimedInteraction] = []
        for row in rows:
            source = event_map[row.event_type]
            weight = self._event_weight(source, watch_percentage=row.watch_percentage)
            if weight <= 0:
                continue
            interactions.append(
                TimedInteraction(
                    user_id=row.user_id,
                    movie_id=row.movie_id,
                    weight=weight,
                    timestamp=row.created_at,
                    source=source,
                )
            )
        return interactions

    def _load_likes(self) -> list[TimedInteraction]:
        return [
            TimedInteraction(
                user_id=row.user_id,
                movie_id=row.movie_id,
                weight=self.weights.get("like", 4.0),
                timestamp=row.created_at,
                source="like",
            )
            for row in Like.objects.filter(movie__status=MovieStatus.RELEASED).only(
                "user_id", "movie_id", "created_at"
            )
        ]

    def _load_ratings(self) -> list[TimedInteraction]:
        interactions: list[TimedInteraction] = []
        for row in Rating.objects.filter(movie__status=MovieStatus.RELEASED).only(
            "user_id", "movie_id", "score", "updated_at", "created_at"
        ):
            score = float(row.score)
            if score <= 0:
                continue
            timestamp = row.updated_at or row.created_at
            interactions.append(
                TimedInteraction(
                    user_id=row.user_id,
                    movie_id=row.movie_id,
                    weight=self.weights.get("rating", 3.0) * (score / 10.0),
                    timestamp=timestamp,
                    source="rating",
                )
            )
        return interactions

    def _load_watch_history(self) -> list[TimedInteraction]:
        interactions: list[TimedInteraction] = []
        for row in WatchHistory.objects.filter(movie__status=MovieStatus.RELEASED).only(
            "user_id",
            "movie_id",
            "watch_percentage",
            "completed_at",
            "last_watched_at",
            "created_at",
        ):
            timestamp = row.completed_at or row.last_watched_at or row.created_at or timezone.now()
            if row.is_completed:
                interactions.append(
                    TimedInteraction(
                        user_id=row.user_id,
                        movie_id=row.movie_id,
                        weight=self.weights.get("watch_complete", 5.0),
                        timestamp=timestamp,
                        source="watch_complete",
                    )
                )
            elif row.watch_percentage > 0:
                interactions.append(
                    TimedInteraction(
                        user_id=row.user_id,
                        movie_id=row.movie_id,
                        weight=self._event_weight(
                            "watch_progress", watch_percentage=row.watch_percentage
                        ),
                        timestamp=timestamp,
                        source="watch_progress",
                    )
                )
        return interactions

    def _load_watchlist(self) -> list[TimedInteraction]:
        return [
            TimedInteraction(
                user_id=row.user_id,
                movie_id=row.movie_id,
                weight=self.weights.get("watchlist_add", 1.5),
                timestamp=row.created_at,
                source="watchlist_add",
            )
            for row in Watchlist.objects.filter(movie__status=MovieStatus.RELEASED).only(
                "user_id", "movie_id", "created_at"
            )
        ]

    def _event_weight(self, source: str, *, watch_percentage: int | None = None) -> float:
        base = self.weights.get(source, 0.0)
        if source == "watch_progress" and watch_percentage is not None:
            return base * (watch_percentage / 100.0)
        return base

    @staticmethod
    def dataset_summary(interactions: list[TimedInteraction]) -> dict:
        users = {interaction.user_id for interaction in interactions}
        movies = {interaction.movie_id for interaction in interactions}
        timestamps = [interaction.timestamp for interaction in interactions]
        per_user: dict[UUID, int] = defaultdict(int)
        for interaction in interactions:
            per_user[interaction.user_id] += 1
        return {
            "interaction_count": len(interactions),
            "user_count": len(users),
            "item_count": len(movies),
            "min_timestamp": min(timestamps).isoformat() if timestamps else None,
            "max_timestamp": max(timestamps).isoformat() if timestamps else None,
            "users_with_multiple_interactions": sum(1 for count in per_user.values() if count >= 2),
        }
