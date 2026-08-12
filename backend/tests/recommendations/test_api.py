"""Recommendation API tests."""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework import status

from apps.interactions.models import InteractionEventType, MovieInteraction
from tests.movies.factories import MovieFactory


@pytest.mark.django_db
def test_popular_recommendations_endpoint(api_client, user):
    movie = MovieFactory(title="API Popular")
    MovieInteraction.objects.create(
        user=user,
        movie=movie,
        event_type=InteractionEventType.WATCH_COMPLETE,
    )

    response = api_client.get("/api/v1/recommendations/popular/?limit=5")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["strategy"] == "popular"
    assert response.data["count"] >= 1
    assert response.data["results"][0]["title"] == "API Popular"
    assert "score" in response.data["results"][0]
    assert "reason" in response.data["results"][0]


@pytest.mark.django_db
def test_trending_recommendations_endpoint(api_client, user):
    movie = MovieFactory(title="API Trending")
    row = MovieInteraction.objects.create(
        user=user,
        movie=movie,
        event_type=InteractionEventType.WATCH_COMPLETE,
    )
    MovieInteraction.objects.filter(pk=row.pk).update(
        created_at=timezone.now() - timedelta(hours=1),
    )

    response = api_client.get("/api/v1/recommendations/trending/?window=24&limit=5")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["strategy"] == "trending"
    assert response.data["count"] >= 1
    assert response.data["results"][0]["title"] == "API Trending"


@pytest.mark.django_db
def test_trending_recommendations_empty(api_client):
    response = api_client.get("/api/v1/recommendations/trending/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 0
    assert response.data["results"] == []
