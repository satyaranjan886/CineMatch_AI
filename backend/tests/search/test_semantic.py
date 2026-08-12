"""Semantic search and embedding tests."""

import pytest
from rest_framework import status

from apps.search.services.embeddings import EmbeddingDimensionError, MovieEmbeddingService
from apps.search.services.similarity import (
    SemanticSimilarityService,
    get_semantically_similar_movies,
)
from tests.movies.factories import MovieFactory


@pytest.fixture
def embedding_service(settings):
    settings.EMBEDDING_MODEL_NAME = "mock-embedder"
    settings.EMBEDDING_MODEL_VERSION = "test-v1"
    settings.EMBEDDING_DIMENSIONS = 384
    return MovieEmbeddingService()


@pytest.mark.django_db
def test_embedding_creation(embedding_service):
    movie = MovieFactory(title="Embedding Film", overview="Space exploration mission")

    result = embedding_service.generate_for_movies([movie], batch_size=8)

    assert result.created == 1
    stored = embedding_service.get_embedding(movie.id)
    assert stored is not None
    assert stored.embedding_dimension == 384
    assert len(stored.embedding) == 384
    assert stored.model_name == "mock-embedder"
    assert stored.model_version == "test-v1"


@pytest.mark.django_db
def test_embedding_dimension_validation(embedding_service):
    movie = MovieFactory(title="Invalid Dimension")

    with pytest.raises(EmbeddingDimensionError):
        embedding_service.save_embedding(movie.id, [0.1, 0.2, 0.3])


@pytest.mark.django_db
def test_semantic_similarity_search(embedding_service):
    anchor = MovieFactory(title="Space Odyssey", overview="science fiction space mission")
    similar = MovieFactory(title="Galaxy Quest", overview="science fiction space adventure")
    unrelated = MovieFactory(title="Romantic Dinner", overview="restaurant love story")

    embedding_service.generate_for_movies([anchor, similar, unrelated], batch_size=8)
    results = get_semantically_similar_movies(anchor.id, limit=5)

    assert results
    assert results[0].movie.id == similar.id
    assert results[0].score >= results[-1].score


@pytest.mark.django_db
def test_semantic_similarity_missing_embeddings(embedding_service):
    movie = MovieFactory(title="No Embedding Yet")
    assert get_semantically_similar_movies(movie.id, limit=5) == []


@pytest.mark.django_db
def test_model_version_isolation(embedding_service):
    movie = MovieFactory(title="Versioned Film", overview="space exploration")
    embedding_service.generate_for_movies([movie], batch_size=8)

    other_version = SemanticSimilarityService(model_version="other-version")
    assert other_version.get_semantically_similar_movies(movie.id, limit=5) == []


@pytest.mark.django_db
def test_semantic_search_api(api_client, embedding_service):
    from apps.movies.models import Movie

    space = MovieFactory(title="Space Frontier", overview="science fiction movies about space")
    MovieFactory(title="City Romance", overview="urban love story")

    embedding_service.generate_for_movies(list(Movie.objects.all()), batch_size=8)

    response = api_client.get(
        "/api/v1/search/semantic/",
        {"q": "science fiction movies about space", "limit": 5},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] >= 1
    assert response.data["results"][0]["id"] == str(space.id)
    assert response.data["results"][0]["title"] == space.title
    assert "score" in response.data["results"][0]


@pytest.mark.django_db
def test_semantic_search_api_rejects_empty_query(api_client):
    response = api_client.get("/api/v1/search/semantic/", {"q": "   "})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "q" in response.data
