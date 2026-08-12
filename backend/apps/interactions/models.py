"""User behavioral data models for personalization."""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.common.models import TimeStampedModel, UUIDModel


class InteractionEventType(models.TextChoices):
    IMPRESSION = "impression", "Impression"
    CLICK = "click", "Click"
    OPEN = "open", "Open"
    PLAY = "play", "Play"
    WATCH_START = "watch_start", "Watch Start"
    WATCH_PROGRESS = "watch_progress", "Watch Progress"
    WATCH_COMPLETE = "watch_complete", "Watch Complete"
    LIKE = "like", "Like"
    DISLIKE = "dislike", "Dislike"
    RATING = "rating", "Rating"
    WATCHLIST_ADD = "watchlist_add", "Watchlist Add"
    WATCHLIST_REMOVE = "watchlist_remove", "Watchlist Remove"
    SEARCH = "search", "Search"
    SKIP = "skip", "Skip"


WATCH_EVENT_TYPES = {
    InteractionEventType.WATCH_START,
    InteractionEventType.WATCH_PROGRESS,
    InteractionEventType.WATCH_COMPLETE,
}

PROGRESS_EVENT_TYPES = {
    InteractionEventType.WATCH_PROGRESS,
    InteractionEventType.WATCH_COMPLETE,
}


class MovieInteraction(UUIDModel):
    """Append-only event log feeding analytics and the recommendation pipeline."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="movie_interactions",
    )
    movie = models.ForeignKey(
        "movies.Movie",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="interactions",
    )
    event_type = models.CharField(
        max_length=32, choices=InteractionEventType.choices, db_index=True
    )
    watch_percentage = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    metadata = models.JSONField(default=dict, blank=True)
    idempotency_key = models.CharField(max_length=128, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "movie_interactions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="interactions_user_created_idx"),
            models.Index(
                fields=["user", "event_type", "-created_at"], name="interactions_user_event_idx"
            ),
            models.Index(fields=["movie", "-created_at"], name="interactions_movie_created_idx"),
            models.Index(
                fields=["event_type", "-created_at"], name="interactions_event_created_idx"
            ),
            models.Index(fields=["movie", "event_type"], name="interactions_movie_event_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "idempotency_key"],
                condition=~models.Q(idempotency_key=""),
                name="interactions_user_idempotency_unique",
            ),
        ]

    def __str__(self) -> str:
        movie_label = self.movie_id or "no-movie"
        return f"{self.event_type} by {self.user_id} on {movie_label}"


class WatchHistory(UUIDModel, TimeStampedModel):
    """Latest watch state per user/movie pair."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="watch_history",
    )
    movie = models.ForeignKey(
        "movies.Movie",
        on_delete=models.CASCADE,
        related_name="watch_history_entries",
    )
    watch_percentage = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    last_watched_at = models.DateTimeField(auto_now=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "watch_history"
        ordering = ["-last_watched_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "movie"], name="watch_history_user_movie_unique"
            ),
        ]
        indexes = [
            models.Index(
                fields=["user", "-last_watched_at"], name="watch_history_user_watched_idx"
            ),
            models.Index(fields=["completed_at"], name="watch_hist_completed_idx"),
            models.Index(fields=["user", "completed_at"], name="watch_hist_user_comp_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} watched {self.movie_id} ({self.watch_percentage}%)"

    @property
    def is_completed(self) -> bool:
        return self.completed_at is not None or self.watch_percentage >= 95


class Rating(UUIDModel, TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ratings",
    )
    movie = models.ForeignKey(
        "movies.Movie",
        on_delete=models.CASCADE,
        related_name="ratings",
    )
    score = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        validators=[MinValueValidator(0.5), MaxValueValidator(10.0)],
    )

    class Meta:
        db_table = "ratings"
        constraints = [
            models.UniqueConstraint(fields=["user", "movie"], name="ratings_user_movie_unique"),
        ]
        indexes = [
            models.Index(fields=["movie", "-updated_at"], name="ratings_movie_updated_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} rated {self.movie_id}: {self.score}"


class Like(UUIDModel, TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="likes",
    )
    movie = models.ForeignKey(
        "movies.Movie",
        on_delete=models.CASCADE,
        related_name="likes",
    )

    class Meta:
        db_table = "likes"
        constraints = [
            models.UniqueConstraint(fields=["user", "movie"], name="likes_user_movie_unique"),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} likes {self.movie_id}"


class Watchlist(UUIDModel, TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="watchlist_items",
    )
    movie = models.ForeignKey(
        "movies.Movie",
        on_delete=models.CASCADE,
        related_name="watchlisted_by",
    )

    class Meta:
        db_table = "watchlist"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "movie"], name="watchlist_user_movie_unique"),
        ]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="watchlist_user_created_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} watchlisted {self.movie_id}"
