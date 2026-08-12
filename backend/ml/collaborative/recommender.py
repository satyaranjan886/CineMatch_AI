"""Collaborative filtering inference."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from uuid import UUID

from django.conf import settings
from scipy.sparse import csr_matrix

from ml.collaborative.artifacts import ArtifactMetadata, CollaborativeArtifactStore
from ml.collaborative.dataset import InteractionDataset, InteractionMatrixBuilder, InteractionRecord
from ml.collaborative.model import ALSCollaborativeFilteringModel, RecommendationCandidate


@dataclass(frozen=True)
class CollaborativeRecommendation:
    movie_id: UUID
    score: float


class CollaborativeFilteringRecommender:
    """Serve recommendations from the active versioned CF artifact."""

    def __init__(
        self,
        *,
        version: str,
        model: ALSCollaborativeFilteringModel,
        metadata: ArtifactMetadata,
        live_records: list[InteractionRecord] | None = None,
        artifact_store: CollaborativeArtifactStore | None = None,
    ):
        self.version = version
        self.model = model
        self.metadata = metadata
        self.live_records = live_records or []
        self.artifact_store = artifact_store or CollaborativeArtifactStore()
        self.user_index, self.item_index, self.reverse_item_index = (
            self.artifact_store.build_index_maps(metadata)
        )
        self._live_by_user = self._index_live_records(self.live_records)

    @classmethod
    def from_version(
        cls,
        version: str,
        *,
        live_records: list[InteractionRecord] | None = None,
        artifact_store: CollaborativeArtifactStore | None = None,
    ) -> CollaborativeFilteringRecommender:
        store = artifact_store or CollaborativeArtifactStore()
        store.ensure_local(version)
        if not store.has_version(version):
            raise FileNotFoundError(
                f"No durable CF artifact for version {version!r} under {store.root}"
            )
        metadata = store.load_metadata(version)
        model = store.load_model(version, model_cls=ALSCollaborativeFilteringModel)
        return cls(
            version=version,
            model=model,
            metadata=metadata,
            live_records=live_records,
            artifact_store=store,
        )

    @classmethod
    def from_registry(
        cls,
        artifact,
        *,
        live_records: list[InteractionRecord] | None = None,
    ) -> CollaborativeFilteringRecommender:
        """Load the exact registry version (DB identity), not an arbitrary on-disk file."""
        return cls.from_version(artifact.version, live_records=live_records)

    def recommend_for_user(
        self,
        user_id: UUID,
        *,
        limit: int = 20,
        exclude_movie_ids: set[UUID] | None = None,
    ) -> list[CollaborativeRecommendation]:
        exclude_movie_ids = exclude_movie_ids or set()
        user_idx = self.user_index.get(user_id)
        if user_idx is None:
            return []

        user_row = self._user_items_row(user_id)

        from apps.common.observability.metrics import observe_inference

        with observe_inference(model=f"collaborative:{self.version}"):
            candidates = self.model.recommend(
                user_idx,
                user_row,
                limit=limit * 3 if exclude_movie_ids else limit,
            )
            if exclude_movie_ids:
                filtered: list[RecommendationCandidate] = []
                for candidate in candidates:
                    movie_id = self.reverse_item_index.get(candidate.item_index)
                    if movie_id is None or movie_id in exclude_movie_ids:
                        continue
                    filtered.append(candidate)
                    if len(filtered) >= limit:
                        break
                candidates = filtered
            return self._map_candidates(candidates)

    def user_interaction_count(self, user_id: UUID) -> int:
        return len(self._live_by_user.get(user_id, []))

    def _index_live_records(
        self,
        records: list[InteractionRecord],
    ) -> dict[UUID, list[InteractionRecord]]:
        grouped: dict[UUID, list[InteractionRecord]] = defaultdict(list)
        for record in records:
            if record.movie_id not in self.item_index:
                continue
            grouped[record.user_id].append(record)
        return grouped

    def _user_items_row(self, user_id: UUID) -> csr_matrix:
        rows = []
        cols = []
        data = []
        aggregated: dict[int, float] = {}

        for record in self._live_by_user.get(user_id, []):
            item_idx = self.item_index.get(record.movie_id)
            if item_idx is None:
                continue
            aggregated[item_idx] = max(aggregated.get(item_idx, 0.0), record.weight)

        for item_idx, weight in aggregated.items():
            rows.append(0)
            cols.append(item_idx)
            data.append(weight)

        return csr_matrix(
            (data, (rows, cols)),
            shape=(1, len(self.metadata.item_ids)),
            dtype=float,
        )

    def _map_candidates(
        self,
        candidates: list[RecommendationCandidate],
    ) -> list[CollaborativeRecommendation]:
        recommendations: list[CollaborativeRecommendation] = []
        seen: set[UUID] = set()
        for candidate in candidates:
            movie_id = self.reverse_item_index.get(candidate.item_index)
            if movie_id is None:
                continue
            if movie_id in seen:
                continue
            seen.add(movie_id)
            recommendations.append(
                CollaborativeRecommendation(movie_id=movie_id, score=candidate.score)
            )
        return recommendations


class ActiveCollaborativeRecommender:
    """Resolve the active artifact and serve recommendations."""

    _cached_version: str | None = None
    _cached_recommender: CollaborativeFilteringRecommender | None = None
    _cached_live_fingerprint: tuple[int, int] | None = None
    _cached_live_dataset: InteractionDataset | None = None
    _cached_live_built_at: float | None = None
    _live_dataset_ttl_seconds: float = 60.0

    @classmethod
    def invalidate(cls) -> None:
        cls._cached_version = None
        cls._cached_recommender = None
        cls._cached_live_fingerprint = None
        cls._cached_live_dataset = None
        cls._cached_live_built_at = None

    def get_recommender(self) -> CollaborativeFilteringRecommender | None:
        from apps.recommendations.models import CollaborativeModelArtifact

        active = (
            CollaborativeModelArtifact.objects.filter(is_active=True)
            .order_by("-trained_at")
            .only(
                "version",
                "trained_at",
                "is_active",
                "artifact_path",
                "model_name",
                "dataset_version",
                "metrics",
            )
            .first()
        )
        if active is None:
            return None

        live_dataset = self.build_live_dataset()
        fingerprint = (live_dataset.interaction_count, live_dataset.user_count)

        if (
            self._cached_recommender is not None
            and self._cached_version == active.version
            and self._cached_live_fingerprint == fingerprint
        ):
            return self._cached_recommender

        recommender = CollaborativeFilteringRecommender.from_registry(
            active,
            live_records=live_dataset.records,
        )
        self.__class__._cached_version = active.version
        self.__class__._cached_recommender = recommender
        self.__class__._cached_live_fingerprint = fingerprint
        return recommender

    def recommend_for_user(
        self,
        user_id: UUID,
        *,
        limit: int = 20,
        exclude_movie_ids: set[UUID] | None = None,
    ) -> list[CollaborativeRecommendation]:
        recommender = self.get_recommender()
        if recommender is None:
            return []
        return recommender.recommend_for_user(
            user_id,
            limit=limit,
            exclude_movie_ids=exclude_movie_ids,
        )

    def user_interaction_count(self, user_id: UUID) -> int:
        """
        Cold-start probe without rebuilding the full interaction matrix.

        Prefer the in-process recommender index when warm; otherwise use cheap
        per-user counts from source tables.
        """
        if self._cached_recommender is not None:
            return self._cached_recommender.user_interaction_count(user_id)

        from apps.interactions.models import Like, Rating, WatchHistory, Watchlist

        return (
            Like.objects.filter(user_id=user_id).count()
            + Rating.objects.filter(user_id=user_id).count()
            + WatchHistory.objects.filter(user_id=user_id).count()
            + Watchlist.objects.filter(user_id=user_id).count()
        )

    @classmethod
    def build_live_dataset(cls) -> InteractionDataset:
        import time

        now = time.monotonic()
        if (
            cls._cached_live_dataset is not None
            and cls._cached_live_built_at is not None
            and (now - cls._cached_live_built_at) < cls._live_dataset_ttl_seconds
        ):
            return cls._cached_live_dataset

        dataset = InteractionMatrixBuilder().build()
        cls._cached_live_dataset = dataset
        cls._cached_live_built_at = now
        return dataset

    @staticmethod
    def cold_start_threshold() -> int:
        return getattr(settings, "CF_MIN_USER_INTERACTIONS", 3)
