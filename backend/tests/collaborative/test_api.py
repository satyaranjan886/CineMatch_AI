"""Collaborative recommendation API tests."""

import pytest
from rest_framework import status

from apps.interactions.models import Like
from ml.collaborative.recommender import ActiveCollaborativeRecommender
from ml.pipelines.collaborative import run_collaborative_training_pipeline
from tests.movies.factories import MovieFactory


@pytest.fixture(autouse=True)
def reset_recommender_cache():
    ActiveCollaborativeRecommender.invalidate()
    yield
    ActiveCollaborativeRecommender.invalidate()


@pytest.fixture
def trained_model(db, tmp_path, settings, user, other_user):
    settings.MEDIA_ROOT = tmp_path
    settings.CF_MODEL_ARTIFACT_DIR = "collaborative_models"
    settings.CF_ALS_FACTORS = 8
    settings.CF_ALS_ITERATIONS = 8
    settings.CF_MIN_USER_INTERACTIONS = 2

    movies = [MovieFactory(title=f"API Movie {index}") for index in range(8)]
    for movie in movies[:4]:
        Like.objects.create(user=user, movie=movie)
    for movie in movies[2:6]:
        Like.objects.create(user=other_user, movie=movie)

    run_collaborative_training_pipeline()
    return movies


@pytest.mark.django_db
def test_collaborative_api_requires_authentication(api_client):
    response = api_client.get("/api/v1/recommendations/collaborative/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_collaborative_api_returns_recommendations(auth_client, user, trained_model):
    response = auth_client.get("/api/v1/recommendations/collaborative/?limit=5")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["strategy"] == "collaborative"
    assert response.data["count"] >= 1
    assert "score" in response.data["results"][0]
    assert response.data["fallback"] is False


@pytest.mark.django_db
def test_collaborative_api_cold_start_fallback(auth_client, trained_model):
    from apps.accounts.models import User

    cold_user = User.objects.create_user(email="cold-api@example.com", password="test-pass-123")
    Like.objects.create(user=cold_user, movie=trained_model[0])

    login = auth_client.post(
        "/api/v1/auth/login/",
        {"email": cold_user.email, "password": "test-pass-123"},
        format="json",
    )
    auth_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

    response = auth_client.get("/api/v1/recommendations/collaborative/?limit=5")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["strategy"] == "popular_fallback"
    assert response.data["fallback"] is True
