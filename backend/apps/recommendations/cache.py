"""Redis cache helpers for precomputed recommendation lists.

Cache key contract (django-redis also applies KEY_PREFIX ``cinematch``):

| Surface        | Key pattern                                                              | TTL setting                          |
|----------------|--------------------------------------------------------------------------|--------------------------------------|
| Popular        | ``recommendations:popular:default``                                      | ``RECOMMENDATION_POPULAR_CACHE_TTL`` |
| Trending       | ``recommendations:trending:{window_hours}``                              | ``RECOMMENDATION_TRENDING_CACHE_TTL``|
| Collaborative  | ``recommendations:collaborative:{user_id}``                              | ``RECOMMENDATION_COLLABORATIVE_CACHE_TTL`` |
| Home           | ``recommendations:home:{user_id}:{profile_id}:{version}:{epoch}:{digest}``| ``HYBRID_HOME_CACHE_TTL``            |
| Home epoch     | ``recommendations:home:epoch:{user_id}``                                 | none (monotonic counter)             |

Invalidation:
- Home: bump epoch on interaction / preference signals
- Collaborative: delete per-user key on interaction; wipe pattern after CF train
- Popular / trending: Celery refresh overwrites keys (idempotent)
"""

from __future__ import annotations

import hashlib
import json
import logging
from uuid import UUID

from django.conf import settings
from django.core.cache import cache

from apps.recommendations.base import RecommendationItem
from ml.ranking.types import (
    CandidateFeatures,
    HomeRecommendationResult,
    HomeSection,
    RankedRecommendation,
)

logger = logging.getLogger(__name__)

# Ephemeral observability fields must not change cache key digests.
_CACHE_CONTEXT_IGNORE = frozenset(
    {
        "candidate_count",
        "merged_candidate_count",
        "filtered_candidate_count",
        "recommendation_count",
    }
)


def _serialize_items(items: list[RecommendationItem]) -> str:
    payload = [
        {
            "movie_id": str(item.movie.id),
            "score": item.score,
            "reason": item.reason,
        }
        for item in items
    ]
    return json.dumps(payload)


def _deserialize_items(raw: str) -> list[dict]:
    return json.loads(raw)


def cache_key(base_key: str, extra: str = "default") -> str:
    return f"recommendations:{base_key}:{extra}"


def home_cache_epoch_key(user_id: UUID) -> str:
    return f"recommendations:home:epoch:{user_id}"


def get_home_cache_epoch(user_id: UUID) -> int:
    value = cache.get(home_cache_epoch_key(user_id))
    return int(value or 0)


def bump_home_cache_epoch(user_id: UUID) -> int:
    key = home_cache_epoch_key(user_id)
    try:
        return int(cache.incr(key))
    except ValueError:
        cache.set(key, 1, timeout=None)
        return 1


def home_cache_key(
    *,
    user_id: UUID,
    profile_id: UUID | str,
    version: str,
    context: dict | None = None,
    epoch: int | None = None,
) -> str:
    context = {
        key: value
        for key, value in (context or {}).items()
        if key not in _CACHE_CONTEXT_IGNORE and value is not None
    }
    if context:
        digest = hashlib.sha256(
            json.dumps(context, sort_keys=True, default=str).encode()
        ).hexdigest()[:16]
    else:
        digest = "default"
    epoch_value = get_home_cache_epoch(user_id) if epoch is None else epoch
    return f"recommendations:home:{user_id}:{profile_id}:{version}:{epoch_value}:{digest}"


def _serialize_home_result(result: HomeRecommendationResult) -> str:
    payload = {
        "version": result.version,
        "context": result.context,
        "sections": [
            {
                "name": section.name,
                "algorithm": section.algorithm,
                "model_version": section.model_version,
                "movies": [
                    {
                        "movie_id": str(item.movie.id),
                        "score": item.score,
                        "reason": item.reason,
                        "primary_source": item.primary_source,
                    }
                    for item in section.movies
                ],
            }
            for section in result.sections
        ],
    }
    return json.dumps(payload)


def _deserialize_home_result(raw: str) -> HomeRecommendationResult | None:
    from apps.movies.models import Movie

    payload = json.loads(raw)
    movie_ids: set[UUID] = set()
    for section in payload.get("sections", []):
        for row in section.get("movies", []):
            movie_ids.add(UUID(row["movie_id"]))

    movies = {
        movie.id: movie
        for movie in Movie.objects.filter(id__in=movie_ids).prefetch_related("movie_genres__genre")
    }

    sections: list[HomeSection] = []
    for section in payload.get("sections", []):
        ranked: list[RankedRecommendation] = []
        for row in section.get("movies", []):
            movie = movies.get(UUID(row["movie_id"]))
            if movie is None:
                continue
            ranked.append(
                RankedRecommendation(
                    movie=movie,
                    score=float(row["score"]),
                    reason=row["reason"],
                    features=CandidateFeatures(
                        movie_id=movie.id,
                        sources={row.get("primary_source", "hybrid"): float(row["score"])},
                    ),
                    primary_source=row.get("primary_source", "hybrid"),
                )
            )
        sections.append(
            HomeSection(
                name=section["name"],
                algorithm=section["algorithm"],
                model_version=section["model_version"],
                movies=ranked,
            )
        )

    return HomeRecommendationResult(
        version=payload.get("version", getattr(settings, "RECOMMENDATION_VERSION", "v1")),
        cached=True,
        sections=sections,
        context=payload.get("context", {}),
    )


def get_cached_recommendations(
    base_key: str, extra: str = "default"
) -> list[RecommendationItem] | None:
    from apps.common.observability.metrics import observe_cache
    from apps.movies.models import Movie

    raw = cache.get(cache_key(base_key, extra))
    if raw is None:
        observe_cache(cache_name=f"recommendations_{base_key}", hit=False)
        return None

    observe_cache(cache_name=f"recommendations_{base_key}", hit=True)
    rows = _deserialize_items(raw)
    if not rows:
        return []

    movie_ids = [UUID(row["movie_id"]) for row in rows]
    movies = Movie.objects.filter(id__in=movie_ids).prefetch_related("movie_genres__genre")
    movie_map = {movie.id: movie for movie in movies}

    items: list[RecommendationItem] = []
    for row in rows:
        movie = movie_map.get(UUID(row["movie_id"]))
        if movie is None:
            continue
        items.append(
            RecommendationItem(
                movie=movie,
                score=float(row["score"]),
                reason=row["reason"],
            )
        )
    return items


def set_cached_recommendations(
    base_key: str,
    extra: str,
    items: list[RecommendationItem],
    ttl: int,
) -> None:
    cache.set(cache_key(base_key, extra), _serialize_items(items), timeout=ttl)


def get_cached_home_recommendations(key: str) -> HomeRecommendationResult | None:
    from apps.common.observability.metrics import observe_cache

    raw = cache.get(key)
    if raw is None:
        observe_cache(cache_name="recommendations_home", hit=False)
        return None
    observe_cache(cache_name="recommendations_home", hit=True)
    return _deserialize_home_result(raw)


def set_cached_home_recommendations(key: str, result: HomeRecommendationResult, ttl: int) -> None:
    cache.set(key, _serialize_home_result(result), timeout=ttl)


def invalidate_recommendation_cache(base_key: str, extra: str = "default") -> None:
    cache.delete(cache_key(base_key, extra))


def invalidate_home_recommendations_for_user(
    user, *, profile=None, context: dict | None = None
) -> None:
    # Epoch bump invalidates all version/context variants for this user.
    bump_home_cache_epoch(user.id)


def invalidate_collaborative_for_user(user_id: UUID | str) -> None:
    invalidate_recommendation_cache("collaborative", str(user_id))


def invalidate_all_collaborative_caches() -> None:
    """Clear personalized CF Redis entries after model train (best-effort)."""
    try:
        deleted = cache.delete_pattern("recommendations:collaborative:*")
        logger.info("invalidated collaborative caches", extra={"deleted": deleted})
    except Exception:
        logger.info("collaborative cache pattern delete unsupported; relying on TTL")
