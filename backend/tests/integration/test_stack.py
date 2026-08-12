"""Integration tests: Postgres, Redis, Celery, and recommendation pipeline."""

from __future__ import annotations

import os

import pytest
from django.core.cache import cache
from django.test import override_settings

from apps.recommendations.cache import (
    get_cached_home_recommendations,
    home_cache_key,
    set_cached_home_recommendations,
)
from apps.recommendations.services.hybrid import HybridHomeRecommendationService
from apps.recommendations.tasks import (
    generate_home_recommendations,
    update_popularity_scores,
    update_trending_scores,
)
from apps.search.tasks import generate_movie_embeddings
from config.celery import ping
from ml.ranking.types import HomeRecommendationResult
from tests.movies.factories import MovieFactory


def _redis_available() -> bool:
    url = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
    try:
        import redis

        client = redis.from_url(url, socket_connect_timeout=1)
        return client.ping() is True
    except Exception:
        return False


@pytest.mark.django_db
def test_postgres_movie_persistence_roundtrip():
    movie = MovieFactory(title="Integration Postgres Film")
    from apps.movies.models import Movie

    loaded = Movie.objects.get(pk=movie.id)
    assert loaded.title == "Integration Postgres Film"


@pytest.mark.django_db
def test_django_cache_roundtrip_for_home_payload(user):
    movie = MovieFactory(title="Cache Film")
    result = HomeRecommendationResult(version="test", cached=False, sections=[], context={})
    key = home_cache_key(
        user_id=user.id,
        profile_id="none",
        version="test",
        context={},
    )
    set_cached_home_recommendations(key, result, ttl=60)
    cached = get_cached_home_recommendations(key)
    assert cached is not None
    assert cached.version == "test"
    assert movie.title == "Cache Film"


@pytest.mark.integration
@pytest.mark.skipif(not _redis_available(), reason="Redis is not reachable")
@pytest.mark.django_db
def test_redis_backend_set_get_delete():
    """Exercise real Redis when REDIS_URL is reachable (CI service)."""
    import redis
    from django.conf import settings

    url = os.environ.get("REDIS_URL", getattr(settings, "REDIS_URL", "redis://127.0.0.1:6379/0"))
    client = redis.from_url(url)
    key = "cinematch:integration:probe"
    client.set(key, "ok", ex=30)
    assert client.get(key) == b"ok"
    client.delete(key)
    assert client.get(key) is None


@pytest.mark.django_db
def test_celery_tasks_are_idempotent_and_eager():
    assert ping.delay().get() == "pong"

    MovieFactory(title="Popularity Task Film")
    first = update_popularity_scores()
    second = update_popularity_scores()
    assert first["strategy"] == "popular"
    assert second["strategy"] == "popular"
    assert first["idempotent"] is True
    assert second["count"] == first["count"]

    trending = update_trending_scores()
    assert trending["strategy"] == "trending"
    assert "windows" in trending

    embeddings = generate_movie_embeddings(limit=5)
    assert embeddings["idempotent"] is True
    assert embeddings["processed"] >= 0


@pytest.mark.django_db
def test_recommendation_pipeline_end_to_end(user):
    MovieFactory(title="Pipeline Film A", popularity=50)
    MovieFactory(title="Pipeline Film B", popularity=40)
    cache.clear()

    service = HybridHomeRecommendationService()
    first = service.get_home_recommendations(user=user)
    assert first.sections
    second = service.get_home_recommendations(user=user)
    assert second.cached is True

    warmed = generate_home_recommendations(lookback_hours=24, limit=10)
    assert warmed["strategy"] == "home_precompute"
    assert warmed["idempotent"] is True


@pytest.mark.django_db
@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "integration-override",
        }
    }
)
def test_cache_backend_override_still_serves_recommendations(user):
    MovieFactory(title="Override Cache Film")
    result = HybridHomeRecommendationService().get_home_recommendations(user=user)
    assert len(result.sections) == 6
