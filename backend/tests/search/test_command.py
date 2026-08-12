"""generate_movie_embeddings command tests."""

import pytest
from django.core.management import call_command

from apps.search.models import MovieEmbedding
from tests.movies.factories import MovieFactory


@pytest.mark.django_db
def test_generate_movie_embeddings_missing_only(settings):
    settings.EMBEDDING_PROVIDER_CLASS = "ml.embeddings.mock.MockEmbeddingProvider"
    settings.EMBEDDING_MODEL_NAME = "mock-embedder"
    settings.EMBEDDING_MODEL_VERSION = "cmd-v1"
    settings.EMBEDDING_DIMENSIONS = 384

    first = MovieFactory(title="First")
    second = MovieFactory(title="Second")

    call_command("generate_movie_embeddings", missing_only=True, batch_size=1)

    assert MovieEmbedding.objects.filter(model_version="cmd-v1").count() == 2

    call_command("generate_movie_embeddings", missing_only=True, batch_size=1)
    assert MovieEmbedding.objects.filter(model_version="cmd-v1").count() == 2

    call_command(
        "generate_movie_embeddings",
        movie_id=str(first.id),
        model_version="cmd-v2",
        batch_size=1,
    )
    assert MovieEmbedding.objects.filter(movie=first, model_version="cmd-v2").exists()
    assert not MovieEmbedding.objects.filter(movie=second, model_version="cmd-v2").exists()
