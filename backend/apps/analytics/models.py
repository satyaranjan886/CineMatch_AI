"""Analytics domain models for recommendation platform metrics."""

from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel, UUIDModel


class RecommendationServeEvent(UUIDModel):
    """Immutable log of recommendation responses served to clients."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recommendation_serves",
    )
    algorithm = models.CharField(max_length=64, db_index=True)
    model_version = models.CharField(max_length=64, blank=True, default="")
    surface = models.CharField(max_length=64, blank=True, default="api", db_index=True)
    cached = models.BooleanField(default=False, db_index=True)
    item_count = models.PositiveIntegerField(default=0)
    movie_ids = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    served_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "recommendation_serve_events"
        ordering = ["-served_at"]
        indexes = [
            models.Index(fields=["algorithm", "-served_at"], name="serve_algo_served_idx"),
            models.Index(fields=["cached", "-served_at"], name="serve_cached_served_idx"),
            models.Index(fields=["surface", "-served_at"], name="serve_surface_served_idx"),
        ]


class AnalyticsDailySnapshot(UUIDModel, TimeStampedModel):
    """Precomputed daily aggregates for the admin dashboard."""

    date = models.DateField(unique=True, db_index=True)
    metrics = models.JSONField(default=dict, blank=True)
    recommendation = models.JSONField(default=dict, blank=True)
    users = models.JSONField(default=dict, blank=True)
    ml = models.JSONField(default=dict, blank=True)
    computed_at = models.DateTimeField(db_index=True)

    class Meta:
        db_table = "analytics_daily_snapshots"
        ordering = ["-date"]
