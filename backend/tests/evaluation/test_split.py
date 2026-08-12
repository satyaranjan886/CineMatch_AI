"""Time-aware split tests."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from ml.evaluation.split import temporal_cutoff_split, temporal_leave_one_out
from ml.evaluation.types import TimedInteraction


def _interaction(user, movie, *, days_ago: int, weight: float = 1.0):
    return TimedInteraction(
        user_id=user,
        movie_id=movie,
        weight=weight,
        timestamp=datetime(2024, 1, 10, tzinfo=UTC) - timedelta(days=days_ago),
        source="like",
    )


def test_temporal_leave_one_out_holds_most_recent():
    user = uuid4()
    older = uuid4()
    newer = uuid4()
    fold = temporal_leave_one_out(
        [
            _interaction(user, older, days_ago=5),
            _interaction(user, newer, days_ago=1),
        ]
    )
    assert {item.movie_id for item in fold.train} == {older}
    assert {item.movie_id for item in fold.test} == {newer}


def test_temporal_leave_one_out_skips_single_interaction_users():
    user = uuid4()
    movie = uuid4()
    fold = temporal_leave_one_out([_interaction(user, movie, days_ago=1)])
    assert fold.test == []
    assert len(fold.train) == 1
    assert fold.exclusion_stats["users_excluded_insufficient_history"] == 1


def test_temporal_cutoff_prevents_future_leakage():
    user = uuid4()
    past_a = uuid4()
    past_b = uuid4()
    future = uuid4()
    cutoff = datetime(2024, 1, 8, tzinfo=UTC)
    fold = temporal_cutoff_split(
        [
            _interaction(user, past_a, days_ago=5),
            _interaction(user, past_b, days_ago=4),
            _interaction(user, future, days_ago=0),
        ],
        cutoff,
        min_interactions=2,
    )
    assert {item.movie_id for item in fold.train} == {past_a, past_b}
    assert {item.movie_id for item in fold.test} == {future}
    assert all(item.timestamp < cutoff for item in fold.train)
    assert all(item.timestamp >= cutoff for item in fold.test)
