import uuid

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework import status

from apps.movies.services.similarity import get_similar_movies
from tests.movies.factories import GenreFactory, MovieFactory, MovieGenreFactory


@pytest.fixture
def catalog(db):
    sci_fi = GenreFactory(name="Science Fiction", slug="science-fiction")
    drama = GenreFactory(name="Drama", slug="drama")
    comedy = GenreFactory(name="Comedy", slug="comedy")

    anchor = MovieFactory(
        title="Anchor Film",
        overview="Science fiction mission across distant stars",
        popularity=99,
        vote_average=8.5,
        release_date="2024-01-01",
    )
    MovieGenreFactory(movie=anchor, genre=sci_fi)
    MovieGenreFactory(movie=anchor, genre=drama)

    similar = MovieFactory(
        title="Similar Film",
        overview="Shared science fiction mission across the stars",
        popularity=80,
        vote_average=8.0,
        release_date="2023-01-01",
    )
    MovieGenreFactory(movie=similar, genre=sci_fi)

    other = MovieFactory(
        title="Other Film",
        overview="Suburban comedy about family life",
        popularity=70,
        vote_average=7.0,
        release_date="2022-01-01",
    )
    MovieGenreFactory(movie=other, genre=comedy)

    return {"anchor": anchor, "similar": similar, "other": other, "sci_fi": sci_fi}


@pytest.mark.django_db
def test_list_movies_is_public_and_paginated(api_client, catalog):
    for _ in range(25):
        MovieFactory()

    response = api_client.get("/api/v1/movies/")

    assert response.status_code == status.HTTP_200_OK
    assert "results" in response.data
    assert response.data["count"] >= 28
    assert len(response.data["results"]) == 20


@pytest.mark.django_db
def test_list_movies_supports_genre_and_rating_filters(api_client, catalog):
    response = api_client.get(
        "/api/v1/movies/",
        {"genre": "science-fiction", "min_rating": 8.0, "ordering": "-vote_average"},
    )

    assert response.status_code == status.HTTP_200_OK
    titles = [item["title"] for item in response.data["results"]]
    assert "Anchor Film" in titles
    assert "Similar Film" in titles
    assert "Other Film" not in titles


@pytest.mark.django_db
def test_list_movies_supports_year_filter(api_client, catalog):
    response = api_client.get("/api/v1/movies/", {"year": 2024})

    assert response.status_code == status.HTTP_200_OK
    titles = [item["title"] for item in response.data["results"]]
    assert titles == ["Anchor Film"]


@pytest.mark.django_db
def test_retrieve_movie_detail(api_client, catalog):
    movie = catalog["anchor"]
    response = api_client.get(f"/api/v1/movies/{movie.id}/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["title"] == "Anchor Film"
    assert len(response.data["genres"]) == 2
    assert "actors" in response.data
    assert "directors" in response.data


@pytest.mark.django_db
def test_missing_movie_returns_404(api_client):
    response = api_client.get(f"/api/v1/movies/{uuid.uuid4()}/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_similar_movies_endpoint(api_client, catalog):
    movie = catalog["anchor"]
    response = api_client.get(f"/api/v1/movies/{movie.id}/similar/")

    assert response.status_code == status.HTTP_200_OK
    titles = [item["title"] for item in response.data]
    assert "Similar Film" in titles
    assert titles[0] == "Similar Film"
    assert "Anchor Film" not in titles
    assert "similarity_score" in response.data[0]


@pytest.mark.django_db
def test_similar_service_orders_by_content_similarity(catalog):
    from ml.content_based.index import ContentSimilarityIndex

    ContentSimilarityIndex.invalidate()
    results = get_similar_movies(catalog["anchor"].id)
    assert results[0].movie.title == "Similar Film"


@pytest.mark.django_db
def test_genre_list_and_detail(api_client, catalog):
    list_response = api_client.get("/api/v1/genres/")
    assert list_response.status_code == status.HTTP_200_OK
    assert list_response.data["count"] == 3

    genre = catalog["sci_fi"]
    detail_response = api_client.get(f"/api/v1/genres/{genre.id}/")
    assert detail_response.status_code == status.HTTP_200_OK
    assert detail_response.data["movie_count"] == 2


@pytest.mark.django_db
def test_write_methods_not_allowed(api_client, catalog):
    response = api_client.post("/api/v1/movies/", {"title": "Hack"}, format="json")
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.django_db
def test_keyword_search_filter(api_client, catalog):
    response = api_client.get("/api/v1/movies/", {"search": "Similar"})
    assert response.status_code == status.HTTP_200_OK
    titles = [item["title"] for item in response.data["results"]]
    assert titles == ["Similar Film"]


@pytest.mark.django_db
def test_list_movies_query_count_bounded(api_client, catalog):
    with CaptureQueriesContext(connection) as context:
        response = api_client.get("/api/v1/movies/")

    assert response.status_code == status.HTTP_200_OK
    assert len(context.captured_queries) <= 8


@pytest.mark.django_db
def test_retrieve_movie_query_count_bounded(api_client, catalog):
    movie = catalog["anchor"]

    with CaptureQueriesContext(connection) as context:
        response = api_client.get(f"/api/v1/movies/{movie.id}/")

    assert response.status_code == status.HTTP_200_OK
    assert len(context.captured_queries) <= 6
