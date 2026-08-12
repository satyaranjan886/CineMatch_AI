"""Recommendation scoring unit tests."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.recommendations.scoring.popularity import (
    PopularitySignals,
    bayesian_rating,
    popularity_score,
)
from apps.recommendations.scoring.trending import TrendingEvent, decay_weight, trending_score


def test_bayesian_rating_shrinks_low_sample_toward_global_mean():
    assert bayesian_rating(
        rating_count=1,
        average_rating=10.0,
        global_average=7.0,
        minimum_votes=10.0,
    ) == pytest.approx(7.27, rel=1e-2)


def test_bayesian_rating_returns_global_mean_without_ratings():
    assert (
        bayesian_rating(
            rating_count=0,
            average_rating=9.0,
            global_average=7.0,
            minimum_votes=10.0,
        )
        == 7.0
    )


def test_popularity_score_penalizes_low_unique_users():
    low_sample = PopularitySignals(
        views=50,
        unique_users=1,
        completions=1,
        likes=1,
        rating_count=1,
        average_rating=10.0,
        catalog_popularity=10.0,
        catalog_vote_average=8.0,
        days_since_last_event=0.0,
    )
    high_sample = PopularitySignals(
        views=50,
        unique_users=20,
        completions=10,
        likes=8,
        rating_count=15,
        average_rating=8.5,
        catalog_popularity=10.0,
        catalog_vote_average=8.0,
        days_since_last_event=0.0,
    )

    assert popularity_score(low_sample) < popularity_score(high_sample)


def test_popularity_score_uses_catalog_fallback_without_interactions():
    weak_catalog = PopularitySignals(
        views=0,
        unique_users=0,
        completions=0,
        likes=0,
        rating_count=0,
        average_rating=0.0,
        catalog_popularity=5.0,
        catalog_vote_average=6.0,
        days_since_last_event=None,
    )
    strong_catalog = PopularitySignals(
        views=0,
        unique_users=0,
        completions=0,
        likes=0,
        rating_count=0,
        average_rating=0.0,
        catalog_popularity=90.0,
        catalog_vote_average=9.0,
        days_since_last_event=None,
    )

    assert popularity_score(strong_catalog) > popularity_score(weak_catalog)


def test_decay_weight_halves_at_half_life():
    weight = decay_weight(age_hours=24.0, half_life_hours=24.0)
    assert weight == pytest.approx(0.5, rel=1e-3)


def test_trending_score_favors_recent_events():
    now = timezone.now()
    recent = [
        TrendingEvent(
            event_type="watch_complete", created_at=now - timedelta(hours=1), user_id="u1"
        ),
    ]
    stale = [
        TrendingEvent(
            event_type="watch_complete", created_at=now - timedelta(hours=72), user_id="u1"
        ),
    ]

    recent_score, _ = trending_score(recent, half_life_hours=24.0, now=now)
    stale_score, _ = trending_score(stale, half_life_hours=24.0, now=now)
    assert recent_score > stale_score


def test_trending_score_dampens_single_user_spike():
    now = timezone.now()
    single_user_events = [
        TrendingEvent(
            event_type="watch_complete",
            created_at=now - timedelta(hours=i + 1),
            user_id="u1",
        )
        for i in range(10)
    ]
    multi_user_events = [
        TrendingEvent(
            event_type="watch_complete",
            created_at=now - timedelta(hours=1),
            user_id=f"u{i}",
        )
        for i in range(10)
    ]

    single_score, _ = trending_score(single_user_events, half_life_hours=24.0, now=now)
    multi_score, _ = trending_score(multi_user_events, half_life_hours=24.0, now=now)
    assert multi_score > single_score


def test_trending_score_empty_events():
    score, unique_users = trending_score([])
    assert score == 0.0
    assert unique_users == 0
