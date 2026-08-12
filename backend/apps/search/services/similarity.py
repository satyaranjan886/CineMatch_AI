"""Vector similarity search over movie embeddings."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from pgvector.django import CosineDistance

from apps.movies.models import Movie, MovieStatus
from apps.search.models import MovieEmbedding
from apps.search.services.embeddings import MovieEmbeddingService


@dataclass(frozen=True)
class SemanticMatch:
    movie: Movie
    score: float


class SemanticSimilarityService:
    def __init__(
        self,
        *,
        model_name: str | None = None,
        model_version: str | None = None,
    ):
        self.embedding_service = MovieEmbeddingService(
            model_name=model_name,
            model_version=model_version,
        )
        self.model_name = self.embedding_service.model_name
        self.model_version = self.embedding_service.model_version

    def get_semantically_similar_movies(
        self,
        movie_id: UUID,
        *,
        limit: int = 20,
    ) -> list[SemanticMatch]:
        source = self.embedding_service.get_embedding(movie_id)
        if source is None:
            return []

        queryset = (
            MovieEmbedding.objects.filter(
                model_name=self.model_name,
                model_version=self.model_version,
                movie__status=MovieStatus.RELEASED,
            )
            .exclude(movie_id=movie_id)
            .select_related("movie")
            .prefetch_related("movie__movie_genres__genre")
            .annotate(distance=CosineDistance("embedding", source.embedding))
            .order_by("distance")[:limit]
        )

        matches: list[SemanticMatch] = []
        for row in queryset:
            # Cosine distance for normalized vectors: 0 = identical, 2 = opposite.
            score = max(0.0, 1.0 - float(row.distance))
            matches.append(SemanticMatch(movie=row.movie, score=score))
        return matches

    def search_by_embedding(
        self,
        query_vector: list[float],
        *,
        limit: int = 20,
        exclude_movie_ids: set[UUID] | None = None,
    ) -> list[SemanticMatch]:
        expected = self.embedding_service.embedding_dimension
        if len(query_vector) != expected:
            raise ValueError(
                f"Query embedding dimension {len(query_vector)} does not match expected {expected}."
            )

        queryset = (
            MovieEmbedding.objects.filter(
                model_name=self.model_name,
                model_version=self.model_version,
                movie__status=MovieStatus.RELEASED,
            )
            .select_related("movie")
            .prefetch_related("movie__movie_genres__genre")
            .annotate(distance=CosineDistance("embedding", query_vector))
            .order_by("distance")
        )
        if exclude_movie_ids:
            queryset = queryset.exclude(movie_id__in=exclude_movie_ids)

        matches: list[SemanticMatch] = []
        for row in queryset[:limit]:
            score = max(0.0, 1.0 - float(row.distance))
            matches.append(SemanticMatch(movie=row.movie, score=score))
        return matches

    def search_by_query(self, query: str, *, limit: int = 20) -> list[SemanticMatch]:
        cleaned = query.strip()
        if not cleaned:
            return []
        vector = self.embedding_service.provider.generate_embedding(cleaned)
        return self.search_by_embedding(vector, limit=limit)


def get_semantically_similar_movies(
    movie_id: UUID,
    *,
    limit: int = 20,
    model_name: str | None = None,
    model_version: str | None = None,
) -> list[SemanticMatch]:
    service = SemanticSimilarityService(model_name=model_name, model_version=model_version)
    return service.get_semantically_similar_movies(movie_id, limit=limit)
