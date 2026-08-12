from django.contrib import admin

from apps.analytics.models import AnalyticsDailySnapshot, RecommendationServeEvent


@admin.register(RecommendationServeEvent)
class RecommendationServeEventAdmin(admin.ModelAdmin):
    list_display = ("algorithm", "surface", "cached", "item_count", "user", "served_at")
    list_filter = ("algorithm", "cached", "surface")
    search_fields = ("algorithm", "model_version", "surface")
    readonly_fields = ("movie_ids", "metadata", "served_at")


@admin.register(AnalyticsDailySnapshot)
class AnalyticsDailySnapshotAdmin(admin.ModelAdmin):
    list_display = ("date", "computed_at", "updated_at")
    ordering = ("-date",)
    readonly_fields = ("metrics", "recommendation", "users", "ml", "computed_at")
