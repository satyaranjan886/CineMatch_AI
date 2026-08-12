"""User taste profile built from positive behavioral signals."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from django.conf import settings
from scipy.sparse import csr_matrix

from apps.interactions.models import Like, Rating, WatchHistory
from ml.content_based.index import ContentSimilarityIndex


@dataclass(frozen=True)
class WeightedMovieSignal:
    movie_id: UUID
    weight: float
    source: str


@dataclass
class UserContentProfile:
    user_id: UUID
    vector: csr_matrix | None
    signals: list[WeightedMovieSignal] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return self.vector is None or not self.signals


class UserContentProfileService:
    """Aggregate weighted movie vectors into a single preference representation."""

    def build_profile(self, user) -> UserContentProfile:
        signals = self.collect_signals(user)
        if not signals:
            return UserContentProfile(user_id=user.id, vector=None, signals=[])

        index = ContentSimilarityIndex.get()
        vectors = []
        weights = []
        for signal in signals:
            vector = index.get_vector(signal.movie_id)
            if vector is None:
                continue
            vectors.append(vector)
            weights.append(signal.weight)

        profile_vector = index.engine.weighted_average_vector(vectors, weights)
        return UserContentProfile(user_id=user.id, vector=profile_vector, signals=signals)

    def collect_signals(self, user) -> list[WeightedMovieSignal]:
        like_weight = getattr(settings, "CONTENT_PROFILE_LIKE_WEIGHT", 3.0)
        rating_weight = getattr(settings, "CONTENT_PROFILE_RATING_WEIGHT", 2.5)
        complete_weight = getattr(settings, "CONTENT_PROFILE_COMPLETE_WEIGHT", 2.0)
        history_weight = getattr(settings, "CONTENT_PROFILE_HISTORY_WEIGHT", 1.0)
        min_rating = getattr(settings, "CONTENT_PROFILE_MIN_RATING", 7.0)

        signals: dict[UUID, WeightedMovieSignal] = {}

        def add_signal(movie_id: UUID, weight: float, source: str) -> None:
            if weight <= 0:
                return
            existing = signals.get(movie_id)
            if existing is None or weight > existing.weight:
                signals[movie_id] = WeightedMovieSignal(
                    movie_id=movie_id, weight=weight, source=source
                )

        for movie_id in Like.objects.filter(user=user).values_list("movie_id", flat=True):
            add_signal(movie_id, like_weight, "like")

        for rating in Rating.objects.filter(user=user).select_related("movie"):
            score = float(rating.score)
            if score >= min_rating:
                weight = rating_weight * (score / 10.0)
                add_signal(rating.movie_id, weight, "rating")

        for entry in WatchHistory.objects.filter(user=user).select_related("movie"):
            if entry.is_completed:
                add_signal(entry.movie_id, complete_weight, "completed")
            elif entry.watch_percentage > 0:
                weight = history_weight * (entry.watch_percentage / 100.0)
                add_signal(entry.movie_id, weight, "history")

        return sorted(signals.values(), key=lambda item: (-item.weight, str(item.movie_id)))
