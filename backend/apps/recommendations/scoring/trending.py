"""Trending scoring primitives."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from django.utils import timezone

EVENT_WEIGHTS: dict[str, float] = {
    "watch_complete": 5.0,
    "watch_progress": 3.0,
    "watch_start": 2.5,
    "play": 2.0,
    "rating": 2.0,
    "like": 1.8,
    "watchlist_add": 1.5,
    "open": 1.2,
    "click": 1.0,
    "impression": 0.4,
    "search": 0.3,
    "skip": 0.2,
    "dislike": 0.0,
    "watchlist_remove": 0.0,
}


@dataclass(frozen=True)
class TrendingEvent:
    event_type: str
    created_at: datetime
    user_id: str


def decay_weight(
    *,
    age_hours: float,
    half_life_hours: float,
) -> float:
    """Exponential time decay: weight halves every `half_life_hours`."""
    if age_hours <= 0:
        return 1.0
    lambda_decay = math.log(2.0) / half_life_hours
    return math.exp(-lambda_decay * age_hours)


def trending_score(
    events: list[TrendingEvent],
    *,
    half_life_hours: float = 24.0,
    now: datetime | None = None,
) -> tuple[float, int]:
    """
    Sum time-decayed event weights, dampened by the heaviest single-user
    contribution so one account cannot dominate the chart.
    """
    now = now or timezone.now()
    raw = 0.0
    users: set[str] = set()
    per_user: dict[str, float] = {}

    for event in events:
        age_hours = max((now - event.created_at).total_seconds() / 3600.0, 0.0)
        base_weight = EVENT_WEIGHTS.get(event.event_type, 0.5)
        contribution = base_weight * decay_weight(
            age_hours=age_hours, half_life_hours=half_life_hours
        )
        raw += contribution
        users.add(event.user_id)
        per_user[event.user_id] = per_user.get(event.user_id, 0.0) + contribution

    unique_users = len(users)
    if unique_users == 0:
        return 0.0, 0

    max_user_share = max(per_user.values())
    dampened = raw / math.sqrt(1.0 + max_user_share)
    return dampened, unique_users
