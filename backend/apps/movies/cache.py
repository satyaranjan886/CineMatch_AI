"""Redis cache helpers for movie detail responses."""

from __future__ import annotations

from uuid import UUID

from django.conf import settings
from django.core.cache import cache

# Key: movies:detail:{movie_id}
# Invalidated on Movie / MovieGenre / MovieActor / MovieDirector changes.


def movie_detail_cache_key(movie_id: UUID | str) -> str:
    return f"movies:detail:{movie_id}"


def get_cached_movie_detail(movie_id: UUID | str) -> dict | None:
    return cache.get(movie_detail_cache_key(movie_id))


def set_cached_movie_detail(movie_id: UUID | str, payload: dict) -> None:
    ttl = getattr(settings, "MOVIE_DETAIL_CACHE_TTL", 600)
    cache.set(movie_detail_cache_key(movie_id), payload, timeout=ttl)


def invalidate_movie_detail(movie_id: UUID | str) -> None:
    cache.delete(movie_detail_cache_key(movie_id))
