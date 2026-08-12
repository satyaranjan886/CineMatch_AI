"""Experiment framework tests."""

from datetime import timedelta
from uuid import uuid4

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.analytics.services.logging import log_recommendation_serve
from apps.experiments.assignment import (
    assign_user,
    choose_variant,
    resolve_serving_decision,
)
from apps.experiments.lifecycle import start_experiment, stop_experiment
from apps.experiments.metrics import compute_experiment_results
from apps.experiments.models import (
    Experiment,
    ExperimentAssignment,
    ExperimentStatus,
    ExperimentVariant,
)
from apps.experiments.registry import build_ranking_service, get_model_definition
from apps.interactions.models import InteractionEventType, MovieInteraction
from apps.recommendations.services.hybrid import HybridHomeRecommendationService
from tests.movies.factories import MovieFactory


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        email="exp-staff@example.com",
        password="test-pass-123",
        is_staff=True,
    )


@pytest.fixture
def staff_client(staff_user):
    client = APIClient()
    response = client.post(
        "/api/v1/auth/login/",
        {"email": staff_user.email, "password": "test-pass-123"},
        format="json",
    )
    assert response.status_code == 200
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    return client


@pytest.fixture
def regular_client(user):
    client = APIClient()
    response = client.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": "test-pass-123"},
        format="json",
    )
    assert response.status_code == 200
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    return client


@pytest.fixture
def experiment(db):
    return Experiment.objects.create(
        name="recommendation_v2",
        description="Hybrid v1 vs v2",
        control_model="hybrid_v1",
        treatment_model="hybrid_v2",
        traffic_percentage=50,
        status=ExperimentStatus.DRAFT,
    )


@pytest.mark.django_db
def test_assignment_is_deterministic(experiment, user):
    first = choose_variant(experiment, user.id)
    second = choose_variant(experiment, user.id)
    assert first == second


@pytest.mark.django_db
def test_assignment_is_sticky(experiment, user):
    experiment.status = ExperimentStatus.RUNNING
    experiment.start_date = timezone.now() - timedelta(hours=1)
    experiment.save()

    a = assign_user(experiment, user)
    b = assign_user(experiment, user)
    assert a.id == b.id
    assert ExperimentAssignment.objects.filter(experiment=experiment, user=user).count() == 1


@pytest.mark.django_db
def test_traffic_allocation_respects_percentage(experiment):
    experiment.traffic_percentage = 0
    assert choose_variant(experiment, uuid4()) == ExperimentVariant.CONTROL
    experiment.traffic_percentage = 100
    assert choose_variant(experiment, uuid4()) == ExperimentVariant.TREATMENT


@pytest.mark.django_db
def test_lifecycle_start_and_stop(experiment):
    started = start_experiment(experiment)
    assert started.status == ExperimentStatus.RUNNING
    assert started.start_date is not None

    stopped = stop_experiment(started)
    assert stopped.status == ExperimentStatus.STOPPED
    assert stopped.end_date is not None


@pytest.mark.django_db
def test_model_selection_uses_registry(experiment, user):
    experiment.status = ExperimentStatus.RUNNING
    experiment.start_date = timezone.now() - timedelta(minutes=5)
    experiment.save()

    decision = resolve_serving_decision(user)
    assert decision.experiment_id == experiment.id
    assert decision.model_key in {"hybrid_v1", "hybrid_v2"}
    assert decision.model_version == get_model_definition(decision.model_key).version
    service = build_ranking_service(decision.model_key)
    assert service is not None


@pytest.mark.django_db
def test_hybrid_service_attaches_experiment_context(experiment, user):
    MovieFactory(title="Exp Film")
    experiment.status = ExperimentStatus.RUNNING
    experiment.start_date = timezone.now() - timedelta(minutes=5)
    experiment.save()

    result = HybridHomeRecommendationService().get_home_recommendations(user=user)
    assert result.context.get("experiment_id") == str(experiment.id)
    assert result.context.get("variant") in {
        ExperimentVariant.CONTROL,
        ExperimentVariant.TREATMENT,
    }
    assert result.version in {"hybrid_v1", "hybrid_v2"}


@pytest.mark.django_db
def test_experiment_metrics(experiment, user):
    experiment.status = ExperimentStatus.RUNNING
    experiment.start_date = timezone.now() - timedelta(hours=1)
    experiment.save()
    assignment = assign_user(experiment, user)
    movie = MovieFactory(title="Metric Film")
    log_recommendation_serve(
        algorithm="hybrid_home",
        movie_ids=[movie.id],
        cached=False,
        user=user,
        model_version=assignment.model_key,
        metadata={
            "experiment_id": str(experiment.id),
            "variant": assignment.variant,
            "model_key": assignment.model_key,
        },
    )
    MovieInteraction.objects.create(
        user=user,
        movie=movie,
        event_type=InteractionEventType.CLICK,
    )

    results = compute_experiment_results(experiment)
    variant = results["variants"][assignment.variant]
    assert variant["assigned_users"] == 1
    assert variant["recommendations_served"] == 1
    assert variant["clicks"] == 1
    assert variant["ctr"] == 1.0


@pytest.mark.django_db
def test_experiment_apis_unauthorized(api_client, regular_client, experiment):
    anon = api_client.get("/api/v1/experiments/")
    assert anon.status_code == status.HTTP_401_UNAUTHORIZED

    forbidden = regular_client.get("/api/v1/experiments/")
    assert forbidden.status_code == status.HTTP_403_FORBIDDEN

    forbidden_start = regular_client.post(f"/api/v1/experiments/{experiment.id}/start/")
    assert forbidden_start.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_experiment_admin_api_lifecycle(staff_client):
    create = staff_client.post(
        "/api/v1/experiments/",
        {
            "name": "recommendation_v2",
            "description": "Control hybrid_v1 vs treatment hybrid_v2",
            "control_model": "hybrid_v1",
            "treatment_model": "hybrid_v2",
            "traffic_percentage": 40,
        },
        format="json",
    )
    assert create.status_code == status.HTTP_201_CREATED
    experiment_id = create.data["id"]

    start = staff_client.post(f"/api/v1/experiments/{experiment_id}/start/")
    assert start.status_code == status.HTTP_200_OK
    assert start.data["status"] == ExperimentStatus.RUNNING

    results = staff_client.get(f"/api/v1/experiments/{experiment_id}/results/")
    assert results.status_code == status.HTTP_200_OK
    assert "variants" in results.data

    stop = staff_client.post(f"/api/v1/experiments/{experiment_id}/stop/")
    assert stop.status_code == status.HTTP_200_OK
    assert stop.data["status"] == ExperimentStatus.STOPPED
