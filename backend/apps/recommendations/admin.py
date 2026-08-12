from django.contrib import admin

from apps.recommendations.models import (
    CollaborativeModelArtifact,
    MoviePopularityScore,
    MovieTrendingScore,
    RecommendationEvaluationReport,
)


@admin.register(MoviePopularityScore)
class MoviePopularityScoreAdmin(admin.ModelAdmin):
    list_display = ("movie", "score", "computed_at", "updated_at")
    search_fields = ("movie__title",)
    ordering = ("-score",)


@admin.register(MovieTrendingScore)
class MovieTrendingScoreAdmin(admin.ModelAdmin):
    list_display = ("movie", "window_hours", "score", "unique_users", "computed_at")
    list_filter = ("window_hours",)
    search_fields = ("movie__title",)
    ordering = ("-score",)


@admin.register(CollaborativeModelArtifact)
class CollaborativeModelArtifactAdmin(admin.ModelAdmin):
    list_display = (
        "model_name",
        "version",
        "dataset_version",
        "is_active",
        "user_count",
        "item_count",
        "interaction_count",
        "trained_at",
    )
    list_filter = ("is_active", "model_name")
    search_fields = ("version", "model_name", "dataset_version")
    ordering = ("-trained_at",)
    readonly_fields = (
        "metrics",
        "hyperparameters",
        "trained_at",
        "artifact_path",
        "dataset_version",
        "model_name",
    )


@admin.register(RecommendationEvaluationReport)
class RecommendationEvaluationReportAdmin(admin.ModelAdmin):
    list_display = (
        "model_name",
        "model_version",
        "report_type",
        "sufficient_data",
        "evaluated_at",
    )
    list_filter = ("report_type", "sufficient_data", "model_name")
    search_fields = ("model_name", "model_version", "notes")
    ordering = ("-evaluated_at",)
    readonly_fields = ("dataset_info", "configuration", "metrics", "evaluated_at")
