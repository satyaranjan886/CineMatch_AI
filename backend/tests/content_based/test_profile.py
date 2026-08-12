"""User content profile tests."""

import pytest
from django.utils import timezone

from apps.interactions.models import Like, Rating, WatchHistory
from apps.recommendations.services.content_profile import UserContentProfileService
from tests.movies.factories import MovieFactory


@pytest.mark.django_db
def test_empty_user_profile(user):
    profile = UserContentProfileService().build_profile(user)

    assert profile.is_empty
    assert profile.vector is None
    assert profile.signals == []


@pytest.mark.django_db
def test_profile_weights_strong_positive_signals(user):
    liked = MovieFactory(title="Liked Film", overview="Liked overview")
    rated = MovieFactory(title="Rated Film", overview="Rated overview")
    completed = MovieFactory(title="Completed Film", overview="Completed overview")
    history = MovieFactory(title="History Film", overview="History overview")

    Like.objects.create(user=user, movie=liked)
    Rating.objects.create(user=user, movie=rated, score=9.0)
    WatchHistory.objects.create(
        user=user,
        movie=completed,
        watch_percentage=100,
        completed_at=timezone.now(),
    )
    WatchHistory.objects.create(user=user, movie=history, watch_percentage=40)

    profile = UserContentProfileService().build_profile(user)

    assert not profile.is_empty
    assert profile.vector is not None
    weights = {signal.movie_id: signal.weight for signal in profile.signals}
    assert weights[liked.id] > weights[history.id]
    assert weights[rated.id] > weights[history.id]
