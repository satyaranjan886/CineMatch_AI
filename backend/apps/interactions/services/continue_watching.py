"""Continue-watching calculations."""

from __future__ import annotations

from apps.interactions.models import WatchHistory
from apps.movies.models import Movie

CONTINUE_WATCHING_MIN_PERCENT = 5
CONTINUE_WATCHING_MAX_PERCENT = 94


def get_continue_watching(user, *, limit: int = 20) -> list[WatchHistory]:
    """
    Return in-progress titles ordered by most recently watched.

    A movie is "continue watching" when the user has started it, has not
    completed it, and progress is within a sensible playback band.
    """
    return list(
        WatchHistory.objects.filter(user=user)
        .filter(watch_percentage__gte=CONTINUE_WATCHING_MIN_PERCENT)
        .filter(watch_percentage__lte=CONTINUE_WATCHING_MAX_PERCENT)
        .filter(completed_at__isnull=True)
        .select_related("movie")
        .prefetch_related("movie__movie_genres__genre")
        .order_by("-last_watched_at")[:limit]
    )


def get_continue_watching_movies(user, *, limit: int = 20) -> list[Movie]:
    return [entry.movie for entry in get_continue_watching(user, limit=limit)]
