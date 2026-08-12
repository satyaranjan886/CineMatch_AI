from django.contrib import admin

from apps.movies.models import Actor, Director, Genre, Movie, MovieActor, MovieDirector, MovieGenre


class MovieGenreInline(admin.TabularInline):
    model = MovieGenre
    extra = 1
    autocomplete_fields = ("genre",)


class MovieActorInline(admin.TabularInline):
    model = MovieActor
    extra = 1
    autocomplete_fields = ("actor",)


class MovieDirectorInline(admin.TabularInline):
    model = MovieDirector
    extra = 1
    autocomplete_fields = ("director",)


@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "status",
        "release_date",
        "vote_average",
        "vote_count",
        "popularity",
        "language",
        "updated_at",
    )
    list_filter = ("status", "language", "country", "release_date")
    search_fields = ("title", "original_title", "overview", "tagline")
    ordering = ("-popularity", "title")
    readonly_fields = ("created_at", "updated_at", "search_vector")
    inlines = (MovieGenreInline, MovieActorInline, MovieDirectorInline)
    date_hierarchy = "release_date"


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at")
    search_fields = ("name", "slug")
    ordering = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")


@admin.register(Actor)
class ActorAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)
    ordering = ("name",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Director)
class DirectorAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)
    ordering = ("name",)
    readonly_fields = ("created_at", "updated_at")
