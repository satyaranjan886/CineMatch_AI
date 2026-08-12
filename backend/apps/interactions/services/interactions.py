"""Interaction domain services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.interactions.models import (
    PROGRESS_EVENT_TYPES,
    WATCH_EVENT_TYPES,
    InteractionEventType,
    Like,
    MovieInteraction,
    Rating,
    WatchHistory,
    Watchlist,
)
from apps.movies.models import Movie


class InteractionValidationError(Exception):
    def __init__(self, message: str, *, field: str | None = None):
        self.message = message
        self.field = field
        super().__init__(message)


@dataclass
class InteractionResult:
    interaction: MovieInteraction
    created: bool


def _validate_event_payload(
    event_type: str,
    *,
    movie: Movie | None,
    watch_percentage: int | None,
    metadata: dict[str, Any],
) -> None:
    if event_type == InteractionEventType.SEARCH:
        if not metadata.get("query"):
            raise InteractionValidationError(
                "Search events require metadata.query.", field="metadata"
            )
        return

    if movie is None:
        raise InteractionValidationError(
            "A valid movie is required for this event type.", field="movie_id"
        )

    if event_type in PROGRESS_EVENT_TYPES and watch_percentage is None:
        raise InteractionValidationError(
            "watch_percentage is required for watch progress events.",
            field="watch_percentage",
        )

    if watch_percentage is not None and (watch_percentage < 0 or watch_percentage > 100):
        raise InteractionValidationError(
            "watch_percentage must be between 0 and 100.",
            field="watch_percentage",
        )

    if event_type == InteractionEventType.RATING:
        score = metadata.get("score")
        if score is None:
            raise InteractionValidationError(
                "Rating events require metadata.score.", field="metadata"
            )


@transaction.atomic
def record_interaction(
    *,
    user,
    event_type: str,
    movie: Movie | None = None,
    watch_percentage: int | None = None,
    metadata: dict[str, Any] | None = None,
    idempotency_key: str = "",
) -> InteractionResult:
    metadata = metadata or {}
    _validate_event_payload(
        event_type, movie=movie, watch_percentage=watch_percentage, metadata=metadata
    )

    if idempotency_key:
        existing = MovieInteraction.objects.filter(
            user=user, idempotency_key=idempotency_key
        ).first()
        if existing:
            return InteractionResult(interaction=existing, created=False)

    interaction = MovieInteraction.objects.create(
        user=user,
        movie=movie,
        event_type=event_type,
        watch_percentage=watch_percentage,
        metadata=metadata,
        idempotency_key=idempotency_key,
    )

    if movie is not None:
        if event_type in WATCH_EVENT_TYPES:
            _upsert_watch_history(user, movie, event_type, watch_percentage)
        if event_type == InteractionEventType.LIKE:
            Like.objects.get_or_create(user=user, movie=movie)
        elif event_type == InteractionEventType.DISLIKE:
            Like.objects.filter(user=user, movie=movie).delete()
        elif event_type == InteractionEventType.RATING:
            Rating.objects.update_or_create(
                user=user,
                movie=movie,
                defaults={"score": metadata["score"]},
            )
        elif event_type == InteractionEventType.WATCHLIST_ADD:
            Watchlist.objects.get_or_create(user=user, movie=movie)
        elif event_type == InteractionEventType.WATCHLIST_REMOVE:
            Watchlist.objects.filter(user=user, movie=movie).delete()

    return InteractionResult(interaction=interaction, created=True)


def _upsert_watch_history(
    user, movie: Movie, event_type: str, watch_percentage: int | None
) -> WatchHistory:
    history, _ = WatchHistory.objects.get_or_create(user=user, movie=movie)
    if watch_percentage is not None:
        history.watch_percentage = max(history.watch_percentage, watch_percentage)
    if event_type == InteractionEventType.WATCH_COMPLETE or (
        watch_percentage is not None and watch_percentage >= 95
    ):
        history.watch_percentage = max(history.watch_percentage, watch_percentage or 95)
        history.completed_at = history.completed_at or timezone.now()
    history.save()
    return history


@transaction.atomic
def set_rating(*, user, movie: Movie, score) -> tuple[Rating, bool]:
    rating, created = Rating.objects.update_or_create(
        user=user,
        movie=movie,
        defaults={"score": score},
    )
    MovieInteraction.objects.create(
        user=user,
        movie=movie,
        event_type=InteractionEventType.RATING,
        metadata={"score": float(score)},
    )
    return rating, created


def get_user_rating(*, user, movie: Movie) -> Rating | None:
    return Rating.objects.filter(user=user, movie=movie).first()


@transaction.atomic
def add_like(*, user, movie: Movie) -> tuple[Like, bool]:
    like, created = Like.objects.get_or_create(user=user, movie=movie)
    if created:
        MovieInteraction.objects.create(
            user=user,
            movie=movie,
            event_type=InteractionEventType.LIKE,
        )
    return like, created


@transaction.atomic
def remove_like(*, user, movie: Movie) -> bool:
    deleted, _ = Like.objects.filter(user=user, movie=movie).delete()
    return deleted > 0


@transaction.atomic
def add_to_watchlist(*, user, movie: Movie) -> tuple[Watchlist, bool]:
    item, created = Watchlist.objects.get_or_create(user=user, movie=movie)
    if created:
        MovieInteraction.objects.create(
            user=user,
            movie=movie,
            event_type=InteractionEventType.WATCHLIST_ADD,
        )
    return item, created


@transaction.atomic
def remove_from_watchlist(*, user, movie: Movie) -> bool:
    deleted, _ = Watchlist.objects.filter(user=user, movie=movie).delete()
    if deleted:
        MovieInteraction.objects.create(
            user=user,
            movie=movie,
            event_type=InteractionEventType.WATCHLIST_REMOVE,
        )
    return deleted > 0
