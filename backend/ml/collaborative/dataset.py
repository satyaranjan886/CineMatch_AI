"""Interaction matrix construction for collaborative filtering."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from uuid import UUID

import numpy as np
from django.conf import settings
from scipy.sparse import csr_matrix

from apps.interactions.models import (
    InteractionEventType,
    Like,
    MovieInteraction,
    Rating,
    WatchHistory,
    Watchlist,
)
from apps.movies.models import MovieStatus


@dataclass(frozen=True)
class InteractionRecord:
    user_id: UUID
    movie_id: UUID
    weight: float
    source: str


@dataclass
class InteractionDataset:
    matrix: csr_matrix
    user_ids: list[UUID]
    item_ids: list[UUID]
    user_index: dict[UUID, int] = field(default_factory=dict)
    item_index: dict[UUID, int] = field(default_factory=dict)
    records: list[InteractionRecord] = field(default_factory=list)

    @property
    def user_count(self) -> int:
        return len(self.user_ids)

    @property
    def item_count(self) -> int:
        return len(self.item_ids)

    @property
    def interaction_count(self) -> int:
        return self.matrix.nnz

    def user_interaction_count(self, user_id: UUID) -> int:
        index = self.user_index.get(user_id)
        if index is None:
            return 0
        return int(self.matrix[index].nnz)

    def build_matrix_from_records(
        self,
        records: list[InteractionRecord],
    ) -> None:
        aggregated: dict[tuple[UUID, UUID], float] = defaultdict(float)
        for record in records:
            key = (record.user_id, record.movie_id)
            aggregated[key] = max(aggregated[key], record.weight)

        if not aggregated:
            self.matrix = csr_matrix((0, 0), dtype=np.float32)
            self.user_ids = []
            self.item_ids = []
            self.user_index = {}
            self.item_index = {}
            self.records = []
            return

        user_ids = sorted({user_id for user_id, _ in aggregated}, key=str)
        item_ids = sorted({movie_id for _, movie_id in aggregated}, key=str)
        self.user_ids = user_ids
        self.item_ids = item_ids
        self.user_index = {user_id: idx for idx, user_id in enumerate(user_ids)}
        self.item_index = {movie_id: idx for idx, movie_id in enumerate(item_ids)}

        rows: list[int] = []
        cols: list[int] = []
        data: list[float] = []
        cleaned_records: list[InteractionRecord] = []

        for (user_id, movie_id), weight in sorted(
            aggregated.items(), key=lambda item: (str(item[0][0]), str(item[0][1]))
        ):
            if weight <= 0:
                continue
            rows.append(self.user_index[user_id])
            cols.append(self.item_index[movie_id])
            data.append(weight)
            cleaned_records.append(
                InteractionRecord(
                    user_id=user_id,
                    movie_id=movie_id,
                    weight=weight,
                    source="aggregated",
                )
            )

        self.matrix = csr_matrix(
            (data, (rows, cols)),
            shape=(len(user_ids), len(item_ids)),
            dtype=np.float32,
        )
        self.records = cleaned_records


class InteractionMatrixBuilder:
    """Load implicit/explicit feedback and build a weighted user-item matrix."""

    DEFAULT_WEIGHTS = {
        "watch_complete": 5.0,
        "like": 4.0,
        "rating": 3.0,
        "watch_progress": 2.0,
        "watchlist_add": 1.5,
    }

    def __init__(self, *, weights: dict[str, float] | None = None):
        self.weights = weights or getattr(settings, "CF_INTERACTION_WEIGHTS", self.DEFAULT_WEIGHTS)

    def build(self) -> InteractionDataset:
        records = self.load_records()
        records = self.clean_records(records)
        dataset = InteractionDataset(
            matrix=csr_matrix((0, 0), dtype=np.float32),
            user_ids=[],
            item_ids=[],
        )
        dataset.build_matrix_from_records(records)
        return dataset

    def load_records(self) -> list[InteractionRecord]:
        records: list[InteractionRecord] = []

        event_map = {
            InteractionEventType.WATCH_COMPLETE: "watch_complete",
            InteractionEventType.WATCH_PROGRESS: "watch_progress",
            InteractionEventType.WATCHLIST_ADD: "watchlist_add",
            InteractionEventType.LIKE: "like",
            InteractionEventType.RATING: "rating",
        }
        interactions = MovieInteraction.objects.filter(
            movie_id__isnull=False,
            movie__status=MovieStatus.RELEASED,
            event_type__in=event_map,
        ).only("user_id", "movie_id", "event_type", "watch_percentage")

        for row in interactions:
            source = event_map[row.event_type]
            weight = self._event_weight(source, watch_percentage=row.watch_percentage)
            records.append(
                InteractionRecord(
                    user_id=row.user_id,
                    movie_id=row.movie_id,
                    weight=weight,
                    source=source,
                )
            )

        for row in Like.objects.filter(movie__status=MovieStatus.RELEASED).only(
            "user_id", "movie_id"
        ):
            records.append(
                InteractionRecord(
                    user_id=row.user_id,
                    movie_id=row.movie_id,
                    weight=self.weights.get("like", 4.0),
                    source="like",
                )
            )

        for row in Rating.objects.filter(movie__status=MovieStatus.RELEASED).only(
            "user_id", "movie_id", "score"
        ):
            score = float(row.score)
            if score <= 0:
                continue
            weight = self.weights.get("rating", 3.0) * (score / 10.0)
            records.append(
                InteractionRecord(
                    user_id=row.user_id,
                    movie_id=row.movie_id,
                    weight=weight,
                    source="rating",
                )
            )

        for row in WatchHistory.objects.filter(movie__status=MovieStatus.RELEASED).only(
            "user_id", "movie_id", "watch_percentage", "completed_at"
        ):
            if row.is_completed:
                records.append(
                    InteractionRecord(
                        user_id=row.user_id,
                        movie_id=row.movie_id,
                        weight=self.weights.get("watch_complete", 5.0),
                        source="watch_complete",
                    )
                )
            elif row.watch_percentage > 0:
                records.append(
                    InteractionRecord(
                        user_id=row.user_id,
                        movie_id=row.movie_id,
                        weight=self._event_weight(
                            "watch_progress", watch_percentage=row.watch_percentage
                        ),
                        source="watch_progress",
                    )
                )

        for row in Watchlist.objects.filter(movie__status=MovieStatus.RELEASED).only(
            "user_id", "movie_id"
        ):
            records.append(
                InteractionRecord(
                    user_id=row.user_id,
                    movie_id=row.movie_id,
                    weight=self.weights.get("watchlist_add", 1.5),
                    source="watchlist_add",
                )
            )

        return records

    def clean_records(self, records: list[InteractionRecord]) -> list[InteractionRecord]:
        cleaned: list[InteractionRecord] = []
        for record in records:
            if record.weight <= 0:
                continue
            cleaned.append(record)
        return cleaned

    def _event_weight(self, source: str, *, watch_percentage: int | None = None) -> float:
        base = self.weights.get(source, 0.0)
        if source == "watch_progress" and watch_percentage is not None:
            return base * (watch_percentage / 100.0)
        return base
