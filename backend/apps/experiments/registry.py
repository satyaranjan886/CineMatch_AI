"""Map logical experiment model keys to ranking configurations."""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

from ml.ranking.ranker import RankingService, WeightedRankingModel


@dataclass(frozen=True)
class ModelDefinition:
    key: str
    version: str
    weights: dict[str, float]
    description: str = ""


def _default_weights() -> dict[str, float]:
    return dict(getattr(settings, "RECOMMENDATION_WEIGHTS", {}))


def _hybrid_v2_weights() -> dict[str, float]:
    """Treatment example: slightly more collaborative + content, less popularity."""
    base = _default_weights()
    adjusted = {
        **base,
        "collaborative": base.get("collaborative", 0.3) * 1.15,
        "content": base.get("content", 0.25) * 1.1,
        "popularity": base.get("popularity", 0.1) * 0.7,
        "trending": base.get("trending", 0.1) * 0.85,
    }
    total = sum(adjusted.values()) or 1.0
    return {key: value / total for key, value in adjusted.items()}


def get_model_definition(model_key: str) -> ModelDefinition:
    registry = {
        "hybrid_v1": ModelDefinition(
            key="hybrid_v1",
            version="hybrid_v1",
            weights=_default_weights(),
            description="Baseline weighted hybrid ranker",
        ),
        "hybrid_v2": ModelDefinition(
            key="hybrid_v2",
            version="hybrid_v2",
            weights=_hybrid_v2_weights(),
            description="Treatment hybrid with stronger CF/content weights",
        ),
    }
    if model_key not in registry:
        raise KeyError(f"Unknown experiment model key: {model_key}")
    return registry[model_key]


def build_ranking_service(model_key: str) -> RankingService:
    definition = get_model_definition(model_key)
    return RankingService(WeightedRankingModel(weights=definition.weights))


def list_model_keys() -> list[str]:
    return ["hybrid_v1", "hybrid_v2"]
