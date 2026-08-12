"""Collaborative filtering dataset tests."""

import pytest

from apps.interactions.models import Like, Rating, WatchHistory
from ml.collaborative.dataset import InteractionMatrixBuilder
from tests.movies.factories import MovieFactory


@pytest.mark.django_db
def test_interaction_matrix_aggregates_max_weight_per_pair(user, other_user):
    movie = MovieFactory(title="Matrix Film")
    other_movie = MovieFactory(title="Other Matrix Film")

    Like.objects.create(user=user, movie=movie)
    Rating.objects.create(user=user, movie=movie, score=8.0)
    WatchHistory.objects.create(user=user, movie=movie, watch_percentage=50)
    Like.objects.create(user=other_user, movie=other_movie)

    dataset = InteractionMatrixBuilder().build()

    assert dataset.interaction_count == 2
    assert dataset.user_count == 2
    assert dataset.item_count == 2
    assert dataset.user_interaction_count(user.id) == 1


@pytest.mark.django_db
def test_interaction_matrix_applies_progress_weighting(user):
    movie = MovieFactory(title="Progress Film")
    WatchHistory.objects.create(user=user, movie=movie, watch_percentage=25)

    dataset = InteractionMatrixBuilder(
        weights={
            "watch_complete": 5.0,
            "like": 4.0,
            "rating": 3.0,
            "watch_progress": 2.0,
            "watchlist_add": 1.5,
        }
    ).build()

    user_idx = dataset.user_index[user.id]
    item_idx = dataset.item_index[movie.id]
    weight = dataset.matrix[user_idx, item_idx]
    assert weight == pytest.approx(0.5, rel=1e-3)


@pytest.mark.django_db
def test_interaction_matrix_empty_dataset():
    dataset = InteractionMatrixBuilder().build()
    assert dataset.interaction_count == 0
    assert dataset.user_count == 0
    assert dataset.item_count == 0
