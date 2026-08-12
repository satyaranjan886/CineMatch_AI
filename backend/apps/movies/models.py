"""Movie catalog domain models."""

from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.text import slugify

from apps.common.models import TimeStampedModel, UUIDModel


class Genre(UUIDModel, TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)

    class Meta:
        db_table = "genres"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["slug"], name="genres_slug_idx"),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:120]
        super().save(*args, **kwargs)


class Actor(UUIDModel, TimeStampedModel):
    name = models.CharField(max_length=255, db_index=True)

    class Meta:
        db_table = "actors"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"], name="actors_name_idx"),
        ]

    def __str__(self) -> str:
        return self.name


class Director(UUIDModel, TimeStampedModel):
    name = models.CharField(max_length=255, db_index=True)

    class Meta:
        db_table = "directors"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"], name="directors_name_idx"),
        ]

    def __str__(self) -> str:
        return self.name


class MovieStatus(models.TextChoices):
    RUMOURED = "rumoured", "Rumoured"
    PLANNED = "planned", "Planned"
    IN_PRODUCTION = "in_production", "In Production"
    POST_PRODUCTION = "post_production", "Post Production"
    RELEASED = "released", "Released"
    CANCELED = "canceled", "Canceled"


class MovieQuerySet(models.QuerySet):
    def with_catalog_relations(self):
        return self.prefetch_related(
            "movie_genres__genre",
            "movie_actors__actor",
            "movie_directors__director",
        )

    def released(self):
        return self.filter(status=MovieStatus.RELEASED)


class Movie(UUIDModel, TimeStampedModel):
    title = models.CharField(max_length=255, db_index=True)
    original_title = models.CharField(max_length=255, blank=True)
    overview = models.TextField(blank=True)
    tagline = models.CharField(max_length=500, blank=True)
    release_date = models.DateField(null=True, blank=True, db_index=True)
    runtime = models.PositiveIntegerField(null=True, blank=True)
    language = models.CharField(max_length=10, blank=True, default="en")
    country = models.CharField(max_length=2, blank=True)
    popularity = models.FloatField(default=0.0, db_index=True)
    vote_average = models.FloatField(
        default=0.0,
        db_index=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(10.0)],
    )
    vote_count = models.PositiveIntegerField(default=0)
    poster_url = models.URLField(max_length=500, blank=True)
    backdrop_url = models.URLField(max_length=500, blank=True)
    status = models.CharField(
        max_length=20,
        choices=MovieStatus.choices,
        default=MovieStatus.RELEASED,
        db_index=True,
    )
    # Populated by search indexing jobs in a later phase; enables Postgres full-text search.
    search_vector = SearchVectorField(null=True, editable=False)
    keywords = models.JSONField(default=list, blank=True)

    objects = MovieQuerySet.as_manager()

    class Meta:
        db_table = "movies"
        ordering = ["-popularity", "title"]
        indexes = [
            models.Index(fields=["-popularity", "title"], name="movies_popularity_title_idx"),
            models.Index(fields=["release_date", "-vote_average"], name="movies_date_rating_idx"),
            models.Index(fields=["status", "-popularity"], name="movies_status_popularity_idx"),
            GinIndex(fields=["search_vector"], name="movies_search_vector_gin"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(vote_average__gte=0.0) & models.Q(vote_average__lte=10.0),
                name="movies_vote_average_range",
            ),
            models.CheckConstraint(
                condition=models.Q(vote_count__gte=0),
                name="movies_vote_count_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return self.title

    @property
    def release_year(self) -> int | None:
        return self.release_date.year if self.release_date else None


class MovieGenre(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name="movie_genres")
    genre = models.ForeignKey(Genre, on_delete=models.CASCADE, related_name="movie_genres")

    class Meta:
        db_table = "movie_genres"
        constraints = [
            models.UniqueConstraint(fields=["movie", "genre"], name="movie_genres_unique"),
        ]
        indexes = [
            models.Index(fields=["genre", "movie"], name="movie_genres_genre_movie_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.movie} — {self.genre}"


class MovieActor(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name="movie_actors")
    actor = models.ForeignKey(Actor, on_delete=models.CASCADE, related_name="movie_actors")
    character_name = models.CharField(max_length=255, blank=True)
    billing_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "movie_actors"
        constraints = [
            models.UniqueConstraint(fields=["movie", "actor"], name="movie_actors_unique"),
        ]
        ordering = ["billing_order", "id"]
        indexes = [
            models.Index(fields=["actor", "movie"], name="movie_actors_actor_movie_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.actor} in {self.movie}"


class MovieDirector(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name="movie_directors")
    director = models.ForeignKey(Director, on_delete=models.CASCADE, related_name="movie_directors")

    class Meta:
        db_table = "movie_directors"
        constraints = [
            models.UniqueConstraint(fields=["movie", "director"], name="movie_directors_unique"),
        ]
        indexes = [
            models.Index(fields=["director", "movie"], name="movie_directors_dir_movie_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.director} — {self.movie}"
