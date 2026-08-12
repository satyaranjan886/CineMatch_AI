from django.contrib import admin

from apps.search.models import MovieEmbedding


@admin.register(MovieEmbedding)
class MovieEmbeddingAdmin(admin.ModelAdmin):
    list_display = (
        "movie",
        "model_name",
        "model_version",
        "embedding_dimension",
        "updated_at",
    )
    list_filter = ("model_name", "model_version")
    search_fields = ("movie__title",)
    readonly_fields = ("created_at", "updated_at", "embedding_dimension")
