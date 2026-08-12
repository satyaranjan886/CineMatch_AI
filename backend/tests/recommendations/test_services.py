"""Recommendation service and cache tests."""

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone

from apps.interactions.models import InteractionEventType, Like, MovieInteraction, Rating
from apps.recommendations.cache import (
    cache_key,
    get_cached_recommendations,
    set_cached_recommendations,
)
from apps.recommendations.models import MoviePopularityScore, MovieTrendingScore
from apps.recommendations.services.popularity import PopularityRecommendationService
from apps.recommendations.services.trending import TrendingRecommendationService
from tests.movies.factories import MovieFactory


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def other_user(db):
    from apps.accounts.models import User

    return User.objects.create_user(email="other@example.com", password="test-pass-123")


@pytest.mark.django_db
def test_popularity_service_orders_by_engagement(user, other_user):
    popular = MovieFactory(title="Popular Film", popularity=50, vote_average=8.0)
    obscure = MovieFactory(title="Obscure Film", popularity=5, vote_average=5.0)

    for viewer in [user, other_user, user]:
        MovieInteraction.objects.create(
            user=viewer,
            movie=popular,
            event_type=InteractionEventType.WATCH_COMPLETE,
        )
    MovieInteraction.objects.create(
        user=user,
        movie=popular,
        event_type=InteractionEventType.IMPRESSION,
    )
    Like.objects.create(user=user, movie=popular)
    Rating.objects.create(user=user, movie=popular, score=9.0)

    MovieInteraction.objects.create(
        user=user,
        movie=obscure,
        event_type=InteractionEventType.CLICK,
    )

    service = PopularityRecommendationService()
    result = service.get_recommendations(limit=10)

    assert result.items[0].movie.id == popular.id
    assert result.items[0].score >= result.items[1].score
    assert MoviePopularityScore.objects.filter(movie=popular).exists()


@pytest.mark.django_db
def test_popularity_service_uses_cache_on_second_request(user):
    movie = MovieFactory(title="Cached Popular")
    MovieInteraction.objects.create(
        user=user,
        movie=movie,
        event_type=InteractionEventType.WATCH_COMPLETE,
    )

    service = PopularityRecommendationService()
    first = service.get_recommendations(limit=5)
    assert first.cached is False

    MovieInteraction.objects.create(
        user=user,
        movie=movie,
        event_type=InteractionEventType.WATCH_COMPLETE,
    )

    second = service.get_recommendations(limit=5)
    assert second.cached is True
    assert len(second.items) == len(first.items)


@pytest.mark.django_db
def test_trending_service_respects_window(user):
    movie = MovieFactory(title="Trending Now")
    now = timezone.now()

    stale = MovieInteraction.objects.create(
        user=user,
        movie=movie,
        event_type=InteractionEventType.WATCH_COMPLETE,
    )
    MovieInteraction.objects.filter(pk=stale.pk).update(created_at=now - timedelta(hours=20))

    service = TrendingRecommendationService()
    wide = service.get_recommendations(limit=5, context={"window_hours": 24})
    assert wide.items
    assert wide.items[0].movie.id == movie.id

    narrow = service.get_recommendations(limit=5, context={"window_hours": 12})
    assert narrow.items == []


@pytest.mark.django_db
def test_trending_service_empty_dataset():
    service = TrendingRecommendationService()
    result = service.get_recommendations(limit=10, context={"window_hours": 24})
    assert result.items == []
    assert MovieTrendingScore.objects.count() == 0


@pytest.mark.django_db
def test_popularity_empty_dataset_returns_catalog_fallback():
    MovieFactory(title="Catalog Leader", popularity=95, vote_average=9.0)
    MovieFactory(title="Catalog Laggard", popularity=1, vote_average=4.0)

    service = PopularityRecommendationService()
    result = service.get_recommendations(limit=10)

    assert len(result.items) == 2
    assert result.items[0].score >= result.items[1].score


@pytest.mark.django_db
def test_refresh_cache_writes_redis(user):
    movie = MovieFactory(title="Refresh Target")
    MovieInteraction.objects.create(
        user=user,
        movie=movie,
        event_type=InteractionEventType.PLAY,
    )

    service = PopularityRecommendationService()
    count = service.refresh_cache()
    assert count >= 1

    cached = get_cached_recommendations(service.cache_key, "default")
    assert cached is not None
    assert cached[0].movie.id == movie.id


@pytest.mark.django_db
def test_cache_helpers_round_trip(user):
    movie = MovieFactory(title="Round Trip")
    MovieInteraction.objects.create(
        user=user,
        movie=movie,
        event_type=InteractionEventType.OPEN,
    )
    service = PopularityRecommendationService()
    items = service.compute_scores()

    set_cached_recommendations("popular", "default", items, ttl=60)
    restored = get_cached_recommendations("popular", "default")

    assert restored is not None
    assert restored[0].movie.title == movie.title
    assert cache.get(cache_key("popular", "default")) is not None
