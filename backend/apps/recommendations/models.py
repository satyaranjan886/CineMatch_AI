"""Persisted recommendation scores refreshed by background jobs."""

from django.db import models

from apps.common.models import TimeStampedModel, UUIDModel


class MoviePopularityScore(UUIDModel, TimeStampedModel):
    movie = models.OneToOneField(
        "movies.Movie",
        on_delete=models.CASCADE,
        related_name="popularity_score",
    )
    score = models.FloatField(db_index=True)
    signals = models.JSONField(default=dict, blank=True)
    computed_at = models.DateTimeField(db_index=True)

    class Meta:
        db_table = "movie_popularity_scores"
        ordering = ["-score"]


class MovieTrendingScore(UUIDModel, TimeStampedModel):
    movie = models.ForeignKey(
        "movies.Movie",
        on_delete=models.CASCADE,
        related_name="trending_scores",
    )
    window_hours = models.PositiveIntegerField(db_index=True)
    score = models.FloatField(db_index=True)
    unique_users = models.PositiveIntegerField(default=0)
    computed_at = models.DateTimeField(db_index=True)

    class Meta:
        db_table = "movie_trending_scores"
        constraints = [
            models.UniqueConstraint(
                fields=["movie", "window_hours"],
                name="trending_scores_movie_window_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["window_hours", "-score"], name="trending_window_score_idx"),
        ]
        ordering = ["-score"]


class CollaborativeModelArtifact(UUIDModel, TimeStampedModel):
    """Registry row for a versioned CF artifact on shared/object storage."""

    model_name = models.CharField(max_length=64, default="collaborative_als", db_index=True)
    version = models.CharField(max_length=64, unique=True, db_index=True)
    artifact_path = models.CharField(max_length=512)
    dataset_version = models.CharField(max_length=128, blank=True, default="")
    is_active = models.BooleanField(default=False, db_index=True)
    user_count = models.PositiveIntegerField(default=0)
    item_count = models.PositiveIntegerField(default=0)
    interaction_count = models.PositiveIntegerField(default=0)
    metrics = models.JSONField(default=dict, blank=True)
    hyperparameters = models.JSONField(default=dict, blank=True)
    trained_at = models.DateTimeField(db_index=True)

    class Meta:
        db_table = "collaborative_model_artifacts"
        ordering = ["-trained_at"]
        indexes = [
            models.Index(
                fields=["is_active", "-trained_at"], name="cf_artifact_active_trained_idx"
            ),
            models.Index(fields=["model_name", "-trained_at"], name="cf_artifact_name_trained_idx"),
        ]

    def to_descriptor(self):
        from ml.collaborative.artifacts import ModelArtifactDescriptor

        return ModelArtifactDescriptor(
            model_name=self.model_name,
            model_version=self.version,
            artifact_location=self.artifact_path,
            created_at=self.trained_at.isoformat(),
            dataset_version=self.dataset_version,
            metrics=self.metrics or {},
            is_active=self.is_active,
        )


class RecommendationEvaluationReport(UUIDModel, TimeStampedModel):
    model_name = models.CharField(max_length=64, db_index=True)
    model_version = models.CharField(max_length=64)
    report_type = models.CharField(max_length=32, db_index=True)
    dataset_info = models.JSONField(default=dict, blank=True)
    configuration = models.JSONField(default=dict, blank=True)
    metrics = models.JSONField(default=dict, blank=True)
    sufficient_data = models.BooleanField(default=True, db_index=True)
    notes = models.TextField(blank=True)
    evaluated_at = models.DateTimeField(db_index=True)

    class Meta:
        db_table = "recommendation_evaluation_reports"
        ordering = ["-evaluated_at"]
