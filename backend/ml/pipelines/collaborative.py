"""Collaborative filtering training pipeline entrypoint."""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from ml.collaborative.artifacts import CF_MODEL_NAME
from ml.collaborative.trainer import CollaborativeFilteringTrainer, TrainingResult


@dataclass(frozen=True)
class CollaborativeTrainingReport:
    version: str
    metrics: dict
    user_count: int
    item_count: int
    interaction_count: int
    model_name: str = CF_MODEL_NAME
    dataset_version: str = ""
    artifact_location: str = ""


def run_collaborative_training_pipeline() -> CollaborativeTrainingReport:
    """
    1. load interaction data
    2. clean data
    3. create user/item mappings
    4. construct interaction matrix
    5. train model
    6. evaluate
    7. persist model artifact (versioned path under CF_MODEL_ARTIFACT_DIR)
    8. persist model metadata + activate registry row
    """
    from apps.recommendations.models import CollaborativeModelArtifact

    model_name = getattr(settings, "CF_MODEL_NAME", CF_MODEL_NAME)
    trainer = CollaborativeFilteringTrainer()
    result: TrainingResult = trainer.train()
    metadata = result.metadata
    artifact_location = metadata.artifact_location or str(
        trainer.artifact_store.artifact_dir(result.version)
    )

    with transaction.atomic():
        # Serialize activation so concurrent trains cannot leave multiple actives.
        list(
            CollaborativeModelArtifact.objects.select_for_update().filter(is_active=True).only("id")
        )
        CollaborativeModelArtifact.objects.filter(is_active=True).update(is_active=False)
        artifact = CollaborativeModelArtifact.objects.create(
            model_name=model_name,
            version=result.version,
            artifact_path=artifact_location,
            dataset_version=metadata.dataset_version,
            is_active=True,
            user_count=result.metadata.user_count,
            item_count=result.metadata.item_count,
            interaction_count=result.metadata.interaction_count,
            metrics=result.metadata.metrics,
            hyperparameters=result.metadata.hyperparameters,
            trained_at=timezone.now(),
        )

    from ml.collaborative.recommender import ActiveCollaborativeRecommender

    ActiveCollaborativeRecommender.invalidate()

    return CollaborativeTrainingReport(
        version=artifact.version,
        metrics=artifact.metrics,
        user_count=artifact.user_count,
        item_count=artifact.item_count,
        interaction_count=artifact.interaction_count,
        model_name=artifact.model_name,
        dataset_version=artifact.dataset_version,
        artifact_location=artifact.artifact_path,
    )
