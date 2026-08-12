"""Movie embedding persistence and batch generation."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from django.conf import settings
from django.db import transaction

from apps.movies.models import Movie, MovieStatus
from apps.search.models import MovieEmbedding
from ml.content_based.features import MovieFeatureBuilder
from ml.embeddings.factory import get_embedding_provider


class EmbeddingDimensionError(ValueError):
    """Raised when an embedding vector has the wrong dimension."""


@dataclass(frozen=True)
class EmbeddingBatchResult:
    created: int
    updated: int
    skipped: int
    processed: int


class MovieEmbeddingService:
    def __init__(
        self,
        *,
        model_name: str | None = None,
        model_version: str | None = None,
    ):
        self.model_name = model_name or getattr(
            settings,
            "EMBEDDING_MODEL_NAME",
            "sentence-transformers/all-MiniLM-L6-v2",
        )
        self.model_version = model_version or getattr(settings, "EMBEDDING_MODEL_VERSION", "v1")
        self.feature_builder = MovieFeatureBuilder()
        self.provider = get_embedding_provider(model_name=self.model_name)

    @property
    def embedding_dimension(self) -> int:
        configured = getattr(settings, "EMBEDDING_DIMENSIONS", None)
        if configured:
            return int(configured)
        if hasattr(self.provider, "dimensions"):
            return int(self.provider.dimensions)
        return len(self.provider.generate_embedding("dimension probe"))

    def movies_missing_embeddings(self) -> list[Movie]:
        existing_ids = MovieEmbedding.objects.filter(
            model_name=self.model_name,
            model_version=self.model_version,
        ).values_list("movie_id", flat=True)
        return list(
            Movie.objects.filter(status=MovieStatus.RELEASED)
            .exclude(id__in=existing_ids)
            .with_catalog_relations()
            .order_by("id")
        )

    def generate_for_movies(
        self,
        movies: list[Movie],
        *,
        batch_size: int | None = None,
    ) -> EmbeddingBatchResult:
        batch_size = batch_size or getattr(settings, "EMBEDDING_BATCH_SIZE", 32)
        created = 0
        updated = 0
        skipped = 0
        processed = 0

        for start in range(0, len(movies), batch_size):
            chunk = movies[start : start + batch_size]
            features = self.feature_builder.build_batch(chunk)
            texts = [feature.text for feature in features]
            vectors = self.provider.generate_batch_embeddings(texts)

            for movie, vector in zip(chunk, vectors, strict=True):
                processed += 1
                if not vector:
                    skipped += 1
                    continue
                saved, was_created = self.save_embedding(movie.id, vector)
                if not saved:
                    skipped += 1
                elif was_created:
                    created += 1
                else:
                    updated += 1

        return EmbeddingBatchResult(
            created=created,
            updated=updated,
            skipped=skipped,
            processed=processed,
        )

    def save_embedding(self, movie_id: UUID, vector: list[float]) -> tuple[bool, bool]:
        expected = self.embedding_dimension
        if len(vector) != expected:
            raise EmbeddingDimensionError(
                f"Expected embedding dimension {expected}, received {len(vector)}."
            )

        with transaction.atomic():
            obj, created = MovieEmbedding.objects.update_or_create(
                movie_id=movie_id,
                model_name=self.model_name,
                model_version=self.model_version,
                defaults={
                    "embedding": vector,
                    "embedding_dimension": expected,
                },
            )
        return True, created

    def get_embedding(self, movie_id: UUID) -> MovieEmbedding | None:
        return (
            MovieEmbedding.objects.filter(
                movie_id=movie_id,
                model_name=self.model_name,
                model_version=self.model_version,
            )
            .select_related("movie")
            .first()
        )
