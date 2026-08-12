"""Popularity scoring primitives."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class PopularitySignals:
    views: int
    unique_users: int
    completions: int
    likes: int
    rating_count: int
    average_rating: float
    catalog_popularity: float
    catalog_vote_average: float
    days_since_last_event: float | None


def bayesian_rating(
    *,
    rating_count: int,
    average_rating: float,
    global_average: float,
    minimum_votes: float,
) -> float:
    """IMDB-style weighted rating to shrink low-sample averages toward the global mean."""
    if rating_count <= 0:
        return global_average
    votes = float(rating_count)
    return (votes / (votes + minimum_votes)) * average_rating + (
        minimum_votes / (votes + minimum_votes)
    ) * global_average


def popularity_score(
    signals: PopularitySignals,
    *,
    minimum_votes: float = 10.0,
    global_average: float = 7.0,
    confidence_users_scale: float = 5.0,
) -> float:
    """
    Combine engagement signals with a confidence ramp so titles with very few
    interactions cannot dominate purely due to one or two events.
    """
    bayesian = bayesian_rating(
        rating_count=signals.rating_count,
        average_rating=signals.average_rating,
        global_average=global_average,
        minimum_votes=minimum_votes,
    )

    engagement = (
        1.4 * math.log1p(signals.views)
        + 2.0 * math.log1p(signals.unique_users)
        + 2.2 * math.log1p(signals.completions)
        + 1.6 * math.log1p(signals.likes)
        + 1.8 * (bayesian / 10.0)
    )

    confidence = 1.0 - math.exp(-signals.unique_users / confidence_users_scale)

    recency_boost = 1.0
    if signals.days_since_last_event is not None:
        recency_boost = 1.0 + 0.15 * math.exp(-signals.days_since_last_event / 30.0)

    if signals.unique_users == 0 and signals.rating_count == 0:
        fallback = 0.35 * math.log1p(signals.catalog_popularity) + 0.25 * (
            signals.catalog_vote_average / 10.0
        )
        return fallback * recency_boost

    return engagement * confidence * recency_boost
