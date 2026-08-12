from django.core.management.base import BaseCommand

from apps.movies.models import Movie, MovieStatus
from apps.search.services.embeddings import MovieEmbeddingService


class Command(BaseCommand):
    help = "Generate and persist movie embeddings for semantic search."

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=None,
            help="Number of movies to embed per batch.",
        )
        parser.add_argument(
            "--missing-only",
            action="store_true",
            help="Process only movies that do not yet have embeddings for the model version.",
        )
        parser.add_argument(
            "--model-name",
            type=str,
            default=None,
            help="Embedding model name override.",
        )
        parser.add_argument(
            "--model-version",
            type=str,
            default=None,
            help="Logical model version tag for stored embeddings.",
        )
        parser.add_argument(
            "--movie-id",
            type=str,
            default=None,
            help="Optional single movie UUID to (re)embed.",
        )

    def handle(self, *args, **options):
        service = MovieEmbeddingService(
            model_name=options["model_name"],
            model_version=options["model_version"],
        )

        if options["movie_id"]:
            movies = list(
                Movie.objects.filter(
                    id=options["movie_id"], status=MovieStatus.RELEASED
                ).with_catalog_relations()
            )
            if not movies:
                self.stderr.write(self.style.ERROR("Movie not found or not released."))
                return
        elif options["missing_only"]:
            movies = service.movies_missing_embeddings()
        else:
            movies = list(
                Movie.objects.filter(status=MovieStatus.RELEASED)
                .with_catalog_relations()
                .order_by("id")
            )

        if not movies:
            self.stdout.write(self.style.WARNING("No movies selected for embedding generation."))
            return

        result = service.generate_for_movies(movies, batch_size=options["batch_size"])
        self.stdout.write(
            self.style.SUCCESS(
                "Generated embeddings "
                f"(model={service.model_name}, version={service.model_version}, "
                f"processed={result.processed}, created={result.created}, "
                f"updated={result.updated}, skipped={result.skipped})."
            )
        )
