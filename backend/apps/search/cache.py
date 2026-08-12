"""Redis cache helpers for semantic search responses."""

from __future__ import annotations

import hashlib
import json

from django.conf import settings
from django.core.cache import cache

# Key: search:semantic:{sha256(query|limit|model_name|model_version)[:24]}
# Short TTL; also cleared wholesale when embeddings are regenerated.


def semantic_search_cache_key(
    *,
    query: str,
    limit: int,
    model_name: str,
    model_version: str,
) -> str:
    payload = json.dumps(
        {
            "q": query.strip().lower(),
            "limit": limit,
            "model_name": model_name,
            "model_version": model_version,
        },
        sort_keys=True,
    )
    digest = hashlib.sha256(payload.encode()).hexdigest()[:24]
    return f"search:semantic:{digest}"


def get_cached_semantic_search(key: str) -> dict | None:
    return cache.get(key)


def set_cached_semantic_search(key: str, payload: dict) -> None:
    ttl = getattr(settings, "SEMANTIC_SEARCH_CACHE_TTL", 120)
    cache.set(key, payload, timeout=ttl)


def invalidate_semantic_search_cache() -> None:
    """Best-effort clear of semantic search entries after embedding refresh."""
    try:
        cache.delete_pattern("search:semantic:*")
    except Exception:
        # LocMem / backends without delete_pattern — rely on TTL.
        pass
