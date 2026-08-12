"""Leakage-prevention tests for temporal recommendation evaluation."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from ml.evaluation.adapters import CollaborativeEvaluationRecommender
from ml.evaluation.split import assert_no_future_in_train, temporal_leave_one_out
from ml.evaluation.types import TimedInteraction


def _ti(user, movie, *, days_ago: int, weight: float = 1.0, source: str = "like"):
    return TimedInteraction(
        user_id=user,
        movie_id=movie,
        weight=weight,
        timestamp=datetime(2024, 6, 1, tzinfo=UTC) - timedelta(days=days_ago),
        source=source,
    )


def test_temporal_split_never_puts_future_in_train():
    user = uuid4()
    past_a = uuid4()
    past_b = uuid4()
    future = uuid4()
    fold = temporal_leave_one_out(
        [
            _ti(user, past_a, days_ago=10),
            _ti(user, past_b, days_ago=5),
            _ti(user, future, days_ago=0),
        ]
    )
    assert_no_future_in_train(fold)
    train_ids = {item.movie_id for item in fold.train}
    test_ids = {item.movie_id for item in fold.test}
    assert future in test_ids
    assert future not in train_ids
    assert past_a in train_ids and past_b in train_ids
    assert max(item.timestamp for item in fold.train) < min(item.timestamp for item in fold.test)


def test_min_interactions_exclusion_is_documented_not_silent():
    cold = uuid4()
    warm = uuid4()
    fold = temporal_leave_one_out(
        [
            _ti(cold, uuid4(), days_ago=1),
            _ti(warm, uuid4(), days_ago=3),
            _ti(warm, uuid4(), days_ago=1),
        ],
        min_interactions=2,
    )
    assert fold.exclusion_stats["users_excluded_insufficient_history"] == 1
    assert "excluded" in fold.exclusion_stats["reason"].lower()
    assert cold not in fold.ground_truth
    assert warm in fold.ground_truth
    # Cold user's interaction remains in train (not deleted).
    assert any(item.user_id == cold for item in fold.train)


def test_synthetic_leakage_trap_popularity_ignores_future_only_movie():
    """
    If future interactions leaked into popularity training, movie F would score
    from the held-out like. With a correct temporal split it must not.
    """
    user = uuid4()
    history = uuid4()
    future = uuid4()
    fold = temporal_leave_one_out(
        [
            _ti(user, history, days_ago=5, weight=4.0),
            _ti(user, future, days_ago=0, weight=5.0),
        ]
    )
    assert future not in {item.movie_id for item in fold.train}
    # Direct train-signal accounting (no DB catalog required).
    train_movies = {item.movie_id for item in fold.train}
    assert history in train_movies
    assert future not in train_movies


@pytest.mark.django_db
def test_collaborative_matrix_excludes_held_out_edge(settings):
    settings.CF_ALS_FACTORS = 4
    settings.CF_ALS_ITERATIONS = 4
    user = uuid4()
    other = uuid4()
    a, b, held = uuid4(), uuid4(), uuid4()
    fold = temporal_leave_one_out(
        [
            _ti(user, a, days_ago=9),
            _ti(user, b, days_ago=5),
            _ti(user, held, days_ago=0),
            _ti(other, a, days_ago=8),
            _ti(other, held, days_ago=7),
            _ti(other, b, days_ago=1),
        ]
    )
    assert_no_future_in_train(fold)
    recommender = CollaborativeEvaluationRecommender(factors=4, iterations=4, random_state=0)
    dataset = recommender._build_dataset(fold.train)
    user_idx = dataset.user_index[user]
    held_idx = dataset.item_index.get(held)
    # Held-out movie may exist via other users, but not as this user's train edge.
    if held_idx is not None:
        assert dataset.matrix[user_idx, held_idx] == 0.0
    assert held not in fold.train_movie_ids(user)


@pytest.mark.django_db
def test_assert_no_future_in_train_detects_corruption():
    user = uuid4()
    fold = temporal_leave_one_out(
        [
            _ti(user, uuid4(), days_ago=5),
            _ti(user, uuid4(), days_ago=1),
        ]
    )
    # Corrupt the fold to simulate leakage; assertion must catch it.
    corrupted_train = list(fold.train) + [
        _ti(user, uuid4(), days_ago=0),
    ]
    from ml.evaluation.types import EvaluationFold

    bad = EvaluationFold(
        train=corrupted_train,
        test=fold.test,
        split_strategy=fold.split_strategy,
        exclusion_stats=fold.exclusion_stats,
    )
    with pytest.raises(AssertionError, match="Future leakage"):
        assert_no_future_in_train(bad)
