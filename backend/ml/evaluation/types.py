"""Evaluation framework data types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class TimedInteraction:
    user_id: UUID
    movie_id: UUID
    weight: float
    timestamp: datetime
    source: str


@dataclass(frozen=True)
class EvaluationFold:
    train: list[TimedInteraction]
    test: list[TimedInteraction]
    split_strategy: str
    cutoff: datetime | None = None
    exclusion_stats: dict = field(default_factory=dict)

    @property
    def train_by_user(self) -> dict[UUID, list[TimedInteraction]]:
        grouped: dict[UUID, list[TimedInteraction]] = {}
        for interaction in self.train:
            grouped.setdefault(interaction.user_id, []).append(interaction)
        return grouped

    @property
    def test_by_user(self) -> dict[UUID, list[TimedInteraction]]:
        grouped: dict[UUID, list[TimedInteraction]] = {}
        for interaction in self.test:
            grouped.setdefault(interaction.user_id, []).append(interaction)
        return grouped

    @property
    def ground_truth(self) -> dict[UUID, set[UUID]]:
        return {
            user_id: {interaction.movie_id for interaction in interactions}
            for user_id, interactions in self.test_by_user.items()
        }

    @property
    def relevance_grades(self) -> dict[UUID, dict[UUID, float]]:
        grades: dict[UUID, dict[UUID, float]] = {}
        for user_id, interactions in self.test_by_user.items():
            user_grades: dict[UUID, float] = {}
            for interaction in interactions:
                user_grades[interaction.movie_id] = max(
                    user_grades.get(interaction.movie_id, 0.0),
                    interaction.weight,
                )
            grades[user_id] = user_grades
        return grades

    def train_movie_ids(self, user_id: UUID) -> set[UUID]:
        return {interaction.movie_id for interaction in self.train_by_user.get(user_id, [])}


@dataclass(frozen=True)
class MetricSnapshot:
    precision_at_k: dict[int, float]
    recall_at_k: dict[int, float]
    map_at_k: dict[int, float]
    ndcg_at_k: dict[int, float]
    hit_rate_at_k: dict[int, float]
    evaluated_users: int
    test_interactions: int

    def as_dict(self) -> dict:
        return {
            "precision_at_k": {str(k): round(v, 6) for k, v in self.precision_at_k.items()},
            "recall_at_k": {str(k): round(v, 6) for k, v in self.recall_at_k.items()},
            "map_at_k": {str(k): round(v, 6) for k, v in self.map_at_k.items()},
            "ndcg_at_k": {str(k): round(v, 6) for k, v in self.ndcg_at_k.items()},
            "hit_rate_at_k": {str(k): round(v, 6) for k, v in self.hit_rate_at_k.items()},
            "evaluated_users": self.evaluated_users,
            "test_interactions": self.test_interactions,
        }


@dataclass(frozen=True)
class ModelEvaluationResult:
    model_name: str
    model_version: str
    metrics: MetricSnapshot
    sufficient_data: bool
    notes: str = ""
    configuration: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ComparisonReport:
    generated_at: datetime
    dataset_info: dict
    configuration: dict
    results: list[ModelEvaluationResult]
    sufficient_data: bool
    notes: str = ""

    def as_dict(self) -> dict:
        return {
            "generated_at": self.generated_at.isoformat(),
            "dataset_info": self.dataset_info,
            "configuration": self.configuration,
            "sufficient_data": self.sufficient_data,
            "notes": self.notes,
            "results": [
                {
                    "model_name": result.model_name,
                    "model_version": result.model_version,
                    "sufficient_data": result.sufficient_data,
                    "notes": result.notes,
                    "configuration": result.configuration,
                    "metrics": result.metrics.as_dict(),
                }
                for result in self.results
            ],
        }
