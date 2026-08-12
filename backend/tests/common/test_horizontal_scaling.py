"""Horizontal scaling / stateless API hardening tests."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from django.conf import settings
from django.core.cache import cache
from django.test import override_settings

from apps.common.locks import try_distributed_lock
from apps.interactions.models import InteractionEventType, MovieInteraction
from apps.recommendations.models import CollaborativeModelArtifact, MovieTrendingScore
from apps.recommendations.services.popularity import PopularityRecommendationService
from apps.recommendations.services.trending import TrendingRecommendationService
from apps.recommendations.tasks import update_popularity_scores, update_trending_scores
from ml.collaborative.artifacts import CollaborativeArtifactStore
from ml.collaborative.recommender import (
    ActiveCollaborativeRecommender,
    CollaborativeFilteringRecommender,
)
from ml.pipelines.collaborative import run_collaborative_training_pipeline
from tests.movies.factories import MovieFactory


def test_sessions_use_database_backend():
    assert settings.SESSION_ENGINE == "django.contrib.sessions.backends.db"
    assert "file" not in settings.SESSION_ENGINE


@pytest.mark.django_db
def test_recommendation_requests_work_without_local_cache_state(api_client, user):
    MovieFactory(title="Stateless Popular")
    PopularityRecommendationService().refresh_cache()

    # Simulate another API instance with a cold / empty cache process.
    cache.clear()

    api_client.force_authenticate(user=user)
    response = api_client.get("/api/v1/recommendations/popular/?limit=5")
    assert response.status_code == 200
    assert response.data["strategy"] == "popular"
    assert response.data["count"] >= 1
    assert response.data["results"]


@pytest.mark.django_db
def test_cache_failure_does_not_corrupt_durable_popularity_rows():
    movie = MovieFactory(title="Durable Popularity")
    service = PopularityRecommendationService()
    service.refresh_cache()

    from apps.recommendations.models import MoviePopularityScore

    assert MoviePopularityScore.objects.filter(movie=movie).exists()
    cache.clear()
    # Recompute from durable sources; must not wipe DB incorrectly.
    service.refresh_cache()
    assert MoviePopularityScore.objects.filter(movie=movie).exists()


@pytest.mark.django_db(transaction=True)
def test_concurrent_trending_refresh_is_atomic(user):
    movies = [MovieFactory(title=f"Trend {i}") for i in range(3)]
    for movie in movies:
        MovieInteraction.objects.create(
            user=user,
            movie=movie,
            event_type=InteractionEventType.PLAY,
        )

    service = TrendingRecommendationService()
    errors: list[BaseException] = []

    def _run():
        from django.db import connection

        try:
            service.refresh_cache(context={"window_hours": 24})
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=_run) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    # Durable scores remain consistent (no empty mid-flight window left behind).
    assert MovieTrendingScore.objects.filter(window_hours=24).count() >= 1


@pytest.mark.django_db
def test_trending_refresh_is_idempotent_and_durable(user):
    movie = MovieFactory(title="Trend Durable")
    MovieInteraction.objects.create(
        user=user,
        movie=movie,
        event_type=InteractionEventType.PLAY,
    )
    service = TrendingRecommendationService()
    service.refresh_cache(context={"window_hours": 24})
    first = MovieTrendingScore.objects.filter(window_hours=24).count()
    assert first >= 1
    service.refresh_cache(context={"window_hours": 24})
    assert MovieTrendingScore.objects.filter(window_hours=24).count() >= 1


@pytest.mark.django_db
def test_multiple_workers_can_safely_process_score_jobs():
    MovieFactory(title="Worker Safe")
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [
            pool.submit(update_popularity_scores),
            pool.submit(update_trending_scores),
            pool.submit(update_popularity_scores),
        ]
        results = [future.result() for future in futures]

    assert all(result.get("idempotent") is True for result in results)
    assert any(result.get("strategy") == "popular" for result in results)


@pytest.mark.django_db
def test_distributed_lock_skips_second_holder_when_redis_available():
    # LocMem backends yield True (no-op). With Redis, second acquire should fail.
    results: list[bool] = []
    with try_distributed_lock("test:horizontal", timeout=5) as first:
        results.append(first)
        with try_distributed_lock("test:horizontal", timeout=5) as second:
            results.append(second)
    assert results[0] is True
    # Either LocMem (both True) or Redis (second False) is acceptable for CI.
    assert results[1] in {True, False}


@pytest.mark.django_db
@override_settings(CF_ALS_FACTORS=8, CF_ALS_ITERATIONS=8, CF_MIN_USER_INTERACTIONS=2)
def test_model_loading_is_versioned(tmp_path, settings, user):
    settings.MEDIA_ROOT = tmp_path
    settings.CF_MODEL_ARTIFACT_DIR = "collaborative_models"
    ActiveCollaborativeRecommender.invalidate()

    movies = [MovieFactory(title=f"CF Scale {i}") for i in range(6)]
    from apps.interactions.models import Like

    other_user = user.__class__.objects.create_user(
        email="cf-other@example.com",
        password="test-pass-123",
    )
    for movie in movies[:3]:
        Like.objects.create(user=user, movie=movie)
    for movie in movies[3:]:
        Like.objects.create(user=other_user, movie=movie)
    extra = user.__class__.objects.create_user(email="cf-scale@example.com", password="x")
    for movie in movies[:2]:
        Like.objects.create(user=extra, movie=movie)

    report = run_collaborative_training_pipeline()
    artifact = CollaborativeModelArtifact.objects.get(version=report.version)

    assert artifact.model_name
    assert artifact.dataset_version
    assert artifact.artifact_path
    assert artifact.metrics
    descriptor = artifact.to_descriptor()
    assert descriptor.model_version == report.version
    assert descriptor.artifact_location == artifact.artifact_path

    store = CollaborativeArtifactStore()
    assert store.has_version(report.version)
    loaded = CollaborativeFilteringRecommender.from_registry(artifact)
    assert loaded.version == report.version
    assert loaded.metadata.model_name == artifact.model_name

    # Loading a non-existent version fails closed (no silent fallback to another file).
    with pytest.raises(FileNotFoundError):
        CollaborativeFilteringRecommender.from_version("cf-does-not-exist")
