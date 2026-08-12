from django.contrib import admin

from apps.interactions.models import Like, MovieInteraction, Rating, WatchHistory, Watchlist


@admin.register(MovieInteraction)
class MovieInteractionAdmin(admin.ModelAdmin):
    list_display = ("event_type", "user", "movie", "watch_percentage", "created_at")
    list_filter = ("event_type", "created_at")
    search_fields = ("user__email", "movie__title", "idempotency_key")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)


@admin.register(WatchHistory)
class WatchHistoryAdmin(admin.ModelAdmin):
    list_display = ("user", "movie", "watch_percentage", "last_watched_at", "completed_at")
    search_fields = ("user__email", "movie__title")
    list_filter = ("completed_at",)
    readonly_fields = ("created_at", "updated_at", "last_watched_at")


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ("user", "movie", "score", "updated_at")
    search_fields = ("user__email", "movie__title")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ("user", "movie", "created_at")
    search_fields = ("user__email", "movie__title")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Watchlist)
class WatchlistAdmin(admin.ModelAdmin):
    list_display = ("user", "movie", "created_at")
    search_fields = ("user__email", "movie__title")
    readonly_fields = ("created_at", "updated_at")
