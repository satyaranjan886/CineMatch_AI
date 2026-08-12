"""Collaborative filtering training and artifact tests."""

import pytest

from apps.interactions.models import Like
from apps.recommendations.models import CollaborativeModelArtifact
from ml.collaborative.artifacts import CollaborativeArtifactStore
from ml.collaborative.recommender import (
    ActiveCollaborativeRecommender,
    CollaborativeFilteringRecommender,
)
from ml.collaborative.trainer import CollaborativeFilteringTrainer
from ml.pipelines.collaborative import run_collaborative_training_pipeline
from tests.movies.factories import MovieFactory


@pytest.fixture
def artifact_root(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    settings.CF_MODEL_ARTIFACT_DIR = "collaborative_models"
    settings.CF_ALS_FACTORS = 8
    settings.CF_ALS_ITERATIONS = 8
    settings.CF_MIN_USER_INTERACTIONS = 2
    ActiveCollaborativeRecommender.invalidate()
    return tmp_path / "collaborative_models"


@pytest.fixture
def collaborative_catalog(db, user, other_user):
    movies = [MovieFactory(title=f"CF Movie {index}") for index in range(6)]
    users = [user, other_user]

    for movie in movies[:3]:
        Like.objects.create(user=user, movie=movie)
    for movie in movies[3:]:
        Like.objects.create(user=other_user, movie=movie)

    extra_user = users[0].__class__.objects.create_user(
        email="cf-extra@example.com",
        password="test-pass-123",
    )
    for movie in movies[:2]:
        Like.objects.create(user=extra_user, movie=movie)

    return {"movies": movies, "users": users + [extra_user]}


@pytest.mark.django_db
def test_trainer_persists_versioned_artifact(artifact_root, collaborative_catalog):
    trainer = CollaborativeFilteringTrainer(
        artifact_store=CollaborativeArtifactStore(root=artifact_root),
    )
    result = trainer.train()

    artifact_dir = artifact_root / result.version
    assert (artifact_dir / "model.pkl").exists()
    assert (artifact_dir / "metadata.json").exists()
    assert result.metadata.metrics.get("methodology") == "temporal_leave_one_out"
    assert result.metadata.metrics["evaluated_users"] >= 0
    if result.metadata.metrics.get("sufficient_data"):
        precision = result.metadata.metrics["precision_at_k"]
        assert "5" in precision and "10" in precision
        assert 0.0 <= float(precision["10"]) <= 1.0


@pytest.mark.django_db
def test_training_pipeline_registers_active_artifact(artifact_root, collaborative_catalog):
    report = run_collaborative_training_pipeline()

    artifact = CollaborativeModelArtifact.objects.get(version=report.version)
    assert artifact.is_active is True
    assert CollaborativeModelArtifact.objects.filter(is_active=True).count() == 1
    assert "methodology" in artifact.metrics or artifact.metrics.get("evaluated_users") is not None


@pytest.mark.django_db
def test_recommender_loads_model_and_recommends(artifact_root, collaborative_catalog, user):
    report = run_collaborative_training_pipeline()
    live_dataset = ActiveCollaborativeRecommender.build_live_dataset()
    recommender = CollaborativeFilteringRecommender.from_version(
        report.version,
        live_records=live_dataset.records,
    )

    recommendations = recommender.recommend_for_user(user.id, limit=5)
    assert recommendations
    assert {candidate.movie_id for candidate in recommendations}


@pytest.mark.django_db
def test_recommender_unknown_user_returns_empty(artifact_root, collaborative_catalog):
    report = run_collaborative_training_pipeline()
    recommender = CollaborativeFilteringRecommender.from_version(report.version)

    cold_user = collaborative_catalog["users"][0].__class__.objects.create_user(
        email="never-trained@example.com",
        password="test-pass-123",
    )

    assert recommender.recommend_for_user(cold_user.id, limit=5) == []
