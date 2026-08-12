"""Collaborative recommendation service tests."""

import pytest
from django.core.cache import cache

from apps.interactions.models import Like
from apps.recommendations.services.collaborative import CollaborativeRecommendationService
from ml.collaborative.recommender import ActiveCollaborativeRecommender
from ml.pipelines.collaborative import run_collaborative_training_pipeline
from tests.movies.factories import MovieFactory


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    ActiveCollaborativeRecommender.invalidate()
    yield
    cache.clear()
    ActiveCollaborativeRecommender.invalidate()


@pytest.fixture
def trained_collaborative(db, tmp_path, settings, user, other_user):
    settings.MEDIA_ROOT = tmp_path
    settings.CF_MODEL_ARTIFACT_DIR = "collaborative_models"
    settings.CF_ALS_FACTORS = 8
    settings.CF_ALS_ITERATIONS = 8
    settings.CF_MIN_USER_INTERACTIONS = 2

    movies = [MovieFactory(title=f"Service Movie {index}") for index in range(8)]
    for movie in movies[:4]:
        Like.objects.create(user=user, movie=movie)
    for movie in movies[4:]:
        Like.objects.create(user=other_user, movie=movie)

    run_collaborative_training_pipeline()
    return {"movies": movies, "users": [user, other_user]}


@pytest.mark.django_db
def test_collaborative_service_returns_personalized_results(trained_collaborative, user):
    service = CollaborativeRecommendationService()
    result = service.get_recommendations(user=user, limit=5)

    assert result.strategy == "collaborative"
    assert result.items
    assert result.context.get("fallback") is not True


@pytest.mark.django_db
def test_collaborative_service_cold_start_fallback(trained_collaborative, user):
    cold_user = user.__class__.objects.create_user(
        email="cold-user@example.com",
        password="test-pass-123",
    )
    Like.objects.create(user=cold_user, movie=trained_collaborative["movies"][0])

    service = CollaborativeRecommendationService()
    result = service.get_recommendations(user=cold_user, limit=5)

    assert result.strategy == "popular_fallback"
    assert result.context["fallback"] is True
    assert result.items


@pytest.mark.django_db
def test_collaborative_service_uses_cache(trained_collaborative, user):
    service = CollaborativeRecommendationService()
    first = service.get_recommendations(user=user, limit=5)
    second = service.get_recommendations(user=user, limit=5)

    assert first.cached is False
    assert second.cached is True
    assert len(first.items) == len(second.items)


@pytest.mark.django_db
def test_collaborative_service_excludes_seen_movies(trained_collaborative, user):
    seen_movie = trained_collaborative["movies"][0]
    service = CollaborativeRecommendationService()
    result = service.get_recommendations(user=user, limit=10)

    returned_ids = {item.movie.id for item in result.items}
    assert seen_movie.id not in returned_ids
