"""Cache and Celery task smoke tests for the performance pass."""

from __future__ import annotations

import pytest
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APIClient

from apps.movies.cache import get_cached_movie_detail, movie_detail_cache_key
from apps.recommendations.tasks import update_popularity_scores, update_trending_scores
from tests.movies.factories import MovieFactory


@pytest.mark.django_db
def test_update_popularity_scores_task():
    MovieFactory()
    result = update_popularity_scores()
    assert result["strategy"] == "popular"
    assert result["idempotent"] is True
    assert result["count"] >= 1


@pytest.mark.django_db
def test_update_trending_scores_task():
    result = update_trending_scores()
    assert result["strategy"] == "trending"
    assert result["idempotent"] is True
    assert "windows" in result


@pytest.mark.django_db
def test_movie_detail_is_cached(api_client: APIClient):
    movie = MovieFactory()
    cache.clear()
    first = api_client.get(f"/api/v1/movies/{movie.id}/")
    assert first.status_code == status.HTTP_200_OK
    assert get_cached_movie_detail(movie.id) is not None
    assert cache.get(movie_detail_cache_key(movie.id))["id"] == str(movie.id)

    second = api_client.get(f"/api/v1/movies/{movie.id}/")
    assert second.status_code == status.HTTP_200_OK
    assert second.data["title"] == first.data["title"]
