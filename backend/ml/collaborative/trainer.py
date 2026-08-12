"""Collaborative filtering training orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

from ml.collaborative.artifacts import ArtifactMetadata, CollaborativeArtifactStore
from ml.collaborative.dataset import InteractionDataset, InteractionMatrixBuilder
from ml.collaborative.model import ALSCollaborativeFilteringModel, CollaborativeFilteringModel


@dataclass(frozen=True)
class TrainingResult:
    version: str
    metadata: ArtifactMetadata
    model: CollaborativeFilteringModel
    dataset: InteractionDataset


class CollaborativeFilteringTrainer:
    """End-to-end CF training pipeline."""

    def __init__(
        self,
        *,
        model_cls=ALSCollaborativeFilteringModel,
        artifact_store: CollaborativeArtifactStore | None = None,
    ):
        self.model_cls = model_cls
        self.artifact_store = artifact_store or CollaborativeArtifactStore()

    def train(self) -> TrainingResult:
        dataset = self._load_dataset()
        if dataset.interaction_count == 0:
            raise ValueError("Cannot train collaborative filtering without interaction data.")

        # Production serving model: fit on the full interaction matrix.
        # Temporal evaluation metrics are computed separately and never feed the
        # serving fit (avoids shrinking coverage while still reporting honest metrics).
        final_model = self._build_model()
        final_model.fit(dataset.matrix)
        metrics = self._evaluate_temporal()

        hyperparameters = {
            "algorithm": "als",
            "factors": getattr(settings, "CF_ALS_FACTORS", 64),
            "iterations": getattr(settings, "CF_ALS_ITERATIONS", 15),
            "regularization": getattr(settings, "CF_ALS_REGULARIZATION", 0.01),
            "random_state": getattr(settings, "CF_ALS_RANDOM_STATE", 42),
            "interaction_weights": getattr(settings, "CF_INTERACTION_WEIGHTS", {}),
            "evaluation_methodology": "temporal_leave_one_out",
        }

        version = self.artifact_store.create_version()
        metadata = self.artifact_store.save(
            version=version,
            model=final_model,
            dataset=dataset,
            metrics=metrics,
            hyperparameters=hyperparameters,
            model_name=getattr(settings, "CF_MODEL_NAME", "collaborative_als"),
        )
        return TrainingResult(
            version=version, metadata=metadata, model=final_model, dataset=dataset
        )

    def _load_dataset(self) -> InteractionDataset:
        return InteractionMatrixBuilder().build()

    def _evaluate_temporal(self) -> dict:
        """
        Time-aware offline metrics for CF.

        Uses the shared evaluation framework: historical interactions → train ALS,
        future hold-outs → test. Does not modify the serving model.
        """
        from ml.evaluation.adapters import CollaborativeEvaluationRecommender
        from ml.evaluation.evaluator import evaluate_recommender

        k_values = [int(v) for v in getattr(settings, "EVAL_K_VALUES", [5, 10, 20])]
        for required in (5, 10):
            if required not in k_values:
                k_values.append(required)
        k_values = sorted(set(k_values))
        primary_k = int(getattr(settings, "CF_EVAL_AT_K", 10))
        if primary_k not in k_values:
            k_values.append(primary_k)
            k_values = sorted(set(k_values))

        seed = int(
            getattr(settings, "EVAL_RANDOM_SEED", getattr(settings, "CF_ALS_RANDOM_STATE", 42))
        )
        min_interactions = int(getattr(settings, "EVAL_MIN_INTERACTIONS", 2))

        recommender = CollaborativeEvaluationRecommender(
            factors=getattr(settings, "CF_ALS_FACTORS", 64),
            iterations=getattr(settings, "CF_ALS_ITERATIONS", 15),
            random_state=seed,
        )
        result = evaluate_recommender(
            model_name="collaborative_filtering",
            split="temporal_leave_one_out",
            k_values=k_values,
            min_interactions=min_interactions,
            seed=seed,
            recommender=recommender,
        )

        payload = result.metrics.as_dict()
        payload["methodology"] = "temporal_leave_one_out"
        payload["sufficient_data"] = result.sufficient_data
        payload["notes"] = result.notes
        payload["configuration"] = result.configuration
        # Backward-compatible scalar aliases at primary K.
        payload["primary_k"] = primary_k
        payload["hit_rate_at_k"] = float(result.metrics.hit_rate_at_k.get(primary_k, 0.0))
        payload["precision_at_k_primary"] = float(result.metrics.precision_at_k.get(primary_k, 0.0))
        payload["recall_at_k_primary"] = float(result.metrics.recall_at_k.get(primary_k, 0.0))
        payload["ndcg_at_k_primary"] = float(result.metrics.ndcg_at_k.get(primary_k, 0.0))
        payload["map_at_k_primary"] = float(result.metrics.map_at_k.get(primary_k, 0.0))
        payload["evaluated_users"] = result.metrics.evaluated_users
        payload["held_out_interactions"] = result.metrics.test_interactions
        return payload

    def _build_model(self) -> CollaborativeFilteringModel:
        return self.model_cls(
            factors=getattr(settings, "CF_ALS_FACTORS", 64),
            iterations=getattr(settings, "CF_ALS_ITERATIONS", 15),
            regularization=getattr(settings, "CF_ALS_REGULARIZATION", 0.01),
            random_state=getattr(settings, "CF_ALS_RANDOM_STATE", 42),
        )
