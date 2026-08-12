import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from apps.movies.models import Actor, Director, Genre, Movie, MovieActor, MovieDirector, MovieGenre

DEFAULT_SAMPLE_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "sample_movies.json"


class Command(BaseCommand):
    help = "Import movie catalog metadata from a JSON file or bundled development sample."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            help="Path to a JSON file with genres, actors, directors, and movies.",
        )
        parser.add_argument(
            "--sample",
            action="store_true",
            help="Import bundled development sample data (no copyrighted datasets).",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete existing catalog rows before import.",
        )

    def handle(self, *args, **options):
        file_path = self._resolve_file_path(options)
        payload = self._load_payload(file_path)

        with transaction.atomic():
            if options["clear"]:
                self._clear_catalog()

            genre_map = self._import_genres(payload.get("genres", []))
            actor_map = self._import_people(payload.get("actors", []), Actor)
            director_map = self._import_people(payload.get("directors", []), Director)
            movie_count = self._import_movies(
                payload.get("movies", []),
                genre_map,
                actor_map,
                director_map,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {len(genre_map)} genres, {len(actor_map)} actors, "
                f"{len(director_map)} directors, {movie_count} movies from {file_path.name}."
            )
        )

    def _resolve_file_path(self, options) -> Path:
        if options["sample"]:
            return DEFAULT_SAMPLE_FILE
        if options["file"]:
            return Path(options["file"]).expanduser().resolve()
        raise CommandError("Provide --file PATH or use --sample for development seed data.")

    def _load_payload(self, file_path: Path) -> dict:
        if not file_path.exists():
            raise CommandError(f"File not found: {file_path}")
        with file_path.open(encoding="utf-8") as handle:
            return json.load(handle)

    def _clear_catalog(self) -> None:
        MovieGenre.objects.all().delete()
        MovieActor.objects.all().delete()
        MovieDirector.objects.all().delete()
        Movie.objects.all().delete()
        Genre.objects.all().delete()
        Actor.objects.all().delete()
        Director.objects.all().delete()
        self.stdout.write("Cleared existing catalog data.")

    def _import_genres(self, rows: list[dict]) -> dict[str, Genre]:
        mapping: dict[str, Genre] = {}
        for row in rows:
            slug = row.get("slug") or slugify(row["name"])[:120]
            genre, _ = Genre.objects.update_or_create(
                slug=slug,
                defaults={"name": row["name"]},
            )
            mapping[slug] = genre
        return mapping

    def _import_people(self, rows: list[dict], model):
        mapping: dict[str, model] = {}
        for row in rows:
            person, _ = model.objects.get_or_create(name=row["name"])
            mapping[row["name"]] = person
        return mapping

    def _import_movies(
        self,
        rows: list[dict],
        genre_map: dict[str, Genre],
        actor_map: dict[str, Actor],
        director_map: dict[str, Director],
    ) -> int:
        count = 0
        for row in rows:
            movie, created = Movie.objects.update_or_create(
                title=row["title"],
                defaults={
                    "original_title": row.get("original_title", ""),
                    "overview": row.get("overview", ""),
                    "tagline": row.get("tagline", ""),
                    "release_date": row.get("release_date"),
                    "runtime": row.get("runtime"),
                    "language": row.get("language", "en"),
                    "country": row.get("country", ""),
                    "popularity": row.get("popularity", 0.0),
                    "vote_average": row.get("vote_average", 0.0),
                    "vote_count": row.get("vote_count", 0),
                    "poster_url": row.get("poster_url", ""),
                    "backdrop_url": row.get("backdrop_url", ""),
                    "status": row.get("status", "released"),
                },
            )

            if not created:
                movie.movie_genres.all().delete()
                movie.movie_actors.all().delete()
                movie.movie_directors.all().delete()

            for slug in row.get("genres", []):
                genre = genre_map.get(slug)
                if genre:
                    MovieGenre.objects.create(movie=movie, genre=genre)

            for actor_row in row.get("actors", []):
                actor = actor_map.get(actor_row["name"])
                if actor:
                    MovieActor.objects.create(
                        movie=movie,
                        actor=actor,
                        character_name=actor_row.get("character_name", ""),
                        billing_order=actor_row.get("billing_order", 0),
                    )

            for director_name in row.get("directors", []):
                director = director_map.get(director_name)
                if director:
                    MovieDirector.objects.create(movie=movie, director=director)

            count += 1
        return count
