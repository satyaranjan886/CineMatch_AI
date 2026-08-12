"""Recommendation result types and service interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from apps.movies.models import Movie


@dataclass(frozen=True)
class RecommendationItem:
    movie: Movie
    score: float
    reason: str


@dataclass
class RecommendationResult:
    strategy: str
    items: list[RecommendationItem] = field(default_factory=list)
    cached: bool = False
    context: dict[str, Any] = field(default_factory=dict)


class BaseRecommendationService(ABC):
    """Common interface for non-personalized candidate generators."""

    strategy_name: str
    cache_key: str
    cache_ttl: int

    @abstractmethod
    def compute_scores(self, *, context: dict[str, Any] | None = None) -> list[RecommendationItem]:
        """Compute fresh ranked recommendations from source data."""

    def get_recommendations(
        self,
        *,
        user=None,
        limit: int = 20,
        context: dict[str, Any] | None = None,
    ) -> RecommendationResult:
        from apps.recommendations.cache import (
            get_cached_recommendations,
            set_cached_recommendations,
        )

        context = context or {}
        cache_extra = self._cache_context_key(context)
        cached_items = get_cached_recommendations(self.cache_key, cache_extra)
        if cached_items is not None:
            return RecommendationResult(
                strategy=self.strategy_name,
                items=cached_items[:limit],
                cached=True,
                context=context,
            )

        items = self.compute_scores(context=context)
        set_cached_recommendations(self.cache_key, cache_extra, items, self.cache_ttl)
        return RecommendationResult(
            strategy=self.strategy_name,
            items=items[:limit],
            cached=False,
            context=context,
        )

    def refresh_cache(self, *, context: dict[str, Any] | None = None) -> int:
        from apps.recommendations.cache import set_cached_recommendations

        context = context or {}
        items = self.compute_scores(context=context)
        cache_extra = self._cache_context_key(context)
        set_cached_recommendations(self.cache_key, cache_extra, items, self.cache_ttl)
        return len(items)

    def _cache_context_key(self, context: dict[str, Any]) -> str:
        return str(context.get("window_hours", "default"))
