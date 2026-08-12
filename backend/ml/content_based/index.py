"""Catalog-wide TF-IDF index for content similarity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from django.conf import settings
from django.db.models import Count, Max

from apps.movies.models import Movie, MovieStatus
from ml.content_based.features import MovieFeatureBuilder
from ml.content_based.tfidf import SimilarityMatch, TfidfSimilarityEngine

if TYPE_CHECKING:
    from scipy.sparse import csr_matrix


@dataclass(frozen=True)
class CatalogFingerprint:
    movie_count: int
    latest_update: str | None


class ContentSimilarityIndex:
    """In-memory TF-IDF index rebuilt when the released catalog changes."""

    _cached_engine: TfidfSimilarityEngine | None = None
    _cached_fingerprint: CatalogFingerprint | None = None
    _cached_movies: dict[UUID, Movie] = {}

    @classmethod
    def get(cls) -> ContentSimilarityIndex:
        fingerprint = cls._current_fingerprint()
        if cls._cached_engine is None or cls._cached_fingerprint != fingerprint:
            cls._cached_engine, cls._cached_movies = cls._build_index()
            cls._cached_fingerprint = fingerprint
        return cls(
            engine=cls._cached_engine,
            movies=cls._cached_movies,
        )

    @classmethod
    def invalidate(cls) -> None:
        cls._cached_engine = None
        cls._cached_fingerprint = None
        cls._cached_movies = {}

    def __init__(self, *, engine: TfidfSimilarityEngine, movies: dict[UUID, Movie]):
        self.engine = engine
        self.movies = movies
        self.feature_builder = MovieFeatureBuilder()

    def similar_to(
        self,
        movie_id: UUID,
        *,
        limit: int = 12,
        exclude_ids: set[UUID] | None = None,
    ) -> list[SimilarityMatch]:
        return self.engine.similar_to(movie_id, limit=limit, exclude_ids=exclude_ids)

    def get_vector(self, movie_id: UUID) -> csr_matrix | None:
        return self.engine.get_vector(movie_id)

    def get_movie(self, movie_id: UUID) -> Movie | None:
        return self.movies.get(movie_id)

    @classmethod
    def _current_fingerprint(cls) -> CatalogFingerprint:
        stats = Movie.objects.filter(status=MovieStatus.RELEASED).aggregate(
            movie_count=Count("id"),
            latest_update=Max("updated_at"),
        )
        latest = stats["latest_update"]
        return CatalogFingerprint(
            movie_count=stats["movie_count"] or 0,
            latest_update=latest.isoformat() if latest else None,
        )

    @classmethod
    def _build_index(cls) -> tuple[TfidfSimilarityEngine, dict[UUID, Movie]]:
        movies = list(
            Movie.objects.filter(status=MovieStatus.RELEASED)
            .with_catalog_relations()
            .order_by("id")
        )
        builder = MovieFeatureBuilder()
        features = builder.build_batch(movies)
        engine = TfidfSimilarityEngine(
            max_features=getattr(settings, "CONTENT_SIMILARITY_MAX_FEATURES", 5000),
        )
        engine.fit(
            movie_ids=[movie.id for movie in movies],
            texts=[feature.text for feature in features],
        )
        return engine, {movie.id: movie for movie in movies}
