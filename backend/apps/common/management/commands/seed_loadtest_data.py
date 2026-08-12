"""Seed a reproducible staging dataset for HTTP load tests."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.interactions.models import InteractionEventType, Like, MovieInteraction, Rating
from apps.movies.models import Genre, Movie, MovieGenre, MovieStatus
from apps.search.services.embeddings import MovieEmbeddingService

User = get_user_model()

PASSWORD = "LoadTestPass123!"
USER_PREFIX = "loadtest-user-"
EMAIL_DOMAIN = "loadtest.cinematch.local"
MOVIE_TITLE_PREFIX = "Loadtest Movie "


class Command(BaseCommand):
    help = (
        "Create a reproducible staging dataset for Locust load tests. "
        "Safe to re-run (upserts loadtest-* users and catalog)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--users", type=int, default=50, help="Number of load-test users")
        parser.add_argument("--movies", type=int, default=200, help="Number of released movies")
        parser.add_argument(
            "--interactions-per-user",
            type=int,
            default=12,
            help="Likes/ratings/events seeded per user",
        )
        parser.add_argument(
            "--with-embeddings",
            action="store_true",
            help="Generate embeddings for seeded movies (uses configured provider/mock)",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        user_count = options["users"]
        movie_count = options["movies"]
        interactions_per_user = options["interactions_per_user"]

        genres = self._ensure_genres()
        movies = self._ensure_movies(movie_count, genres)
        users = self._ensure_users(user_count)
        self._ensure_interactions(users, movies, interactions_per_user)

        embedding_rows = 0
        if options["with_embeddings"]:
            embedding_rows = self._ensure_embeddings(movies)

        self.stdout.write(self.style.SUCCESS("Load-test dataset ready:"))
        self.stdout.write(f"  users: {len(users)}")
        self.stdout.write(f"  movies: {len(movies)}")
        self.stdout.write(f"  genres: {len(genres)}")
        self.stdout.write(f"  interactions_per_user: {interactions_per_user}")
        self.stdout.write(f"  embedding_rows: {embedding_rows}")
        self.stdout.write(f"  password: {PASSWORD}")
        self.stdout.write(f"  email_pattern: {USER_PREFIX}N@{EMAIL_DOMAIN}")

    def _ensure_genres(self) -> list[Genre]:
        names = ["Action", "Drama", "Comedy", "Sci-Fi", "Thriller", "Romance"]
        genres = []
        for name in names:
            genre, _ = Genre.objects.get_or_create(
                name=name,
                defaults={"slug": name.lower().replace(" ", "-")},
            )
            genres.append(genre)
        return genres

    def _ensure_movies(self, count: int, genres: list[Genre]) -> list[Movie]:
        movies: list[Movie] = []
        for index in range(count):
            title = f"{MOVIE_TITLE_PREFIX}{index:04d}"
            movie, _ = Movie.objects.update_or_create(
                title=title,
                defaults={
                    "overview": f"Synthetic staging title {index} for HTTP load tests.",
                    "status": MovieStatus.RELEASED,
                    "popularity": float(100 - (index % 100)),
                    "vote_average": 5.0 + (index % 50) / 10.0,
                    "vote_count": 50 + index,
                    "release_date": timezone.now().date() - timedelta(days=index * 3),
                },
            )
            primary = genres[index % len(genres)]
            MovieGenre.objects.get_or_create(movie=movie, genre=primary)
            movies.append(movie)
        return movies

    def _ensure_users(self, count: int) -> list:
        users = []
        for index in range(count):
            email = f"{USER_PREFIX}{index}@{EMAIL_DOMAIN}"
            user, created = User.objects.get_or_create(
                email=email,
                defaults={"is_active": True},
            )
            user.set_password(PASSWORD)
            user.save(update_fields=["password"])
            users.append(user)
        return users

    def _ensure_interactions(self, users, movies, per_user: int) -> None:
        now = timezone.now()
        for user_index, user in enumerate(users):
            for offset in range(per_user):
                movie = movies[(user_index * 3 + offset) % len(movies)]
                Like.objects.get_or_create(user=user, movie=movie)
                Rating.objects.update_or_create(
                    user=user,
                    movie=movie,
                    defaults={"score": Decimal(6 + (offset % 5))},
                )
                interaction_qs = MovieInteraction.objects.filter(
                    user=user,
                    movie=movie,
                    event_type=InteractionEventType.WATCH_COMPLETE,
                )
                if not interaction_qs.exists():
                    interaction = MovieInteraction.objects.create(
                        user=user,
                        movie=movie,
                        event_type=InteractionEventType.WATCH_COMPLETE,
                    )
                    MovieInteraction.objects.filter(pk=interaction.pk).update(
                        created_at=now - timedelta(days=per_user - offset)
                    )

    def _ensure_embeddings(self, movies: list[Movie]) -> int:
        service = MovieEmbeddingService()
        result = service.generate_for_movies(list(movies))
        return int(result.created + result.updated)
