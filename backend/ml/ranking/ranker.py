"""Configuration-driven ranking service."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from django.conf import settings

from ml.ranking.types import CandidateFeatures


class BaseRankingModel(ABC):
    @abstractmethod
    def score(self, features: CandidateFeatures) -> float:
        raise NotImplementedError


class WeightedRankingModel(BaseRankingModel):
    """Baseline weighted linear model; replace with a trained ranker later."""

    def __init__(self, weights: dict[str, float] | None = None):
        self.weights = weights or getattr(settings, "RECOMMENDATION_WEIGHTS", {})

    def score(self, features: CandidateFeatures) -> float:
        content_component = max(features.content_score, features.semantic_score)
        rating_component = max(features.popularity_score, features.rating_quality)

        components = {
            "collaborative": features.collaborative_score,
            "content": content_component,
            "genre_preference": features.genre_affinity,
            "popularity": rating_component,
            "trending": features.trending_score,
            "freshness": features.freshness_score,
            "affinity": max(features.user_affinity, features.interaction_strength),
        }

        total = 0.0
        for key, weight in self.weights.items():
            total += float(weight) * float(components.get(key, 0.0))
        return total


class RankingService:
    def __init__(self, model: BaseRankingModel | None = None):
        self.model = model or WeightedRankingModel()

    def rank(
        self, features_by_movie: dict[UUID, CandidateFeatures]
    ) -> list[tuple[UUID, float, CandidateFeatures]]:
        scored = [
            (movie_id, self.model.score(features), features)
            for movie_id, features in features_by_movie.items()
        ]
        scored.sort(key=lambda row: row[1], reverse=True)
        return scored

    @staticmethod
    def primary_source(features: CandidateFeatures) -> str:
        if not features.sources:
            return "hybrid"
        return max(features.sources.items(), key=lambda item: item[1])[0]
