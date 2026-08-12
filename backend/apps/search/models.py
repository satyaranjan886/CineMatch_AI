"""Semantic search models backed by pgvector."""

from django.contrib.postgres.indexes import OpClass
from django.db import models
from pgvector.django import HnswIndex, VectorField

from apps.common.models import TimeStampedModel, UUIDModel


class MovieEmbedding(UUIDModel, TimeStampedModel):
    """Dense vector representation of a movie for semantic similarity."""

    movie = models.ForeignKey(
        "movies.Movie",
        on_delete=models.CASCADE,
        related_name="embeddings",
    )
    embedding = VectorField(dimensions=384)
    model_name = models.CharField(max_length=128, db_index=True)
    model_version = models.CharField(max_length=64, db_index=True)
    embedding_dimension = models.PositiveIntegerField()

    class Meta:
        db_table = "movie_embeddings"
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["movie", "model_name", "model_version"],
                name="movie_embeddings_movie_model_unique",
            ),
        ]
        indexes = [
            models.Index(
                fields=["model_name", "model_version"],
                name="movie_embeddings_model_idx",
            ),
            HnswIndex(
                OpClass("embedding", name="vector_cosine_ops"),
                name="movie_embed_hnsw_cosine_idx",
                m=16,
                ef_construction=64,
            ),
        ]

    def __str__(self) -> str:
        return f"{self.movie_id} ({self.model_name}@{self.model_version})"
