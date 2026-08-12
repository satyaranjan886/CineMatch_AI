"""Analytics aggregation and permission tests."""

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.analytics.models import AnalyticsDailySnapshot, RecommendationServeEvent
from apps.analytics.services.aggregation import compute_daily_snapshot, get_dashboard_payload
from apps.analytics.services.logging import log_recommendation_serve
from apps.interactions.models import InteractionEventType, MovieInteraction
from apps.recommendations.models import CollaborativeModelArtifact, RecommendationEvaluationReport
from tests.movies.factories import MovieFactory


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        email="staff@example.com",
        password="test-pass-123",
        is_staff=True,
    )


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


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
def test_dashboard_requires_authentication(api_client):
    response = api_client.get("/api/v1/analytics/dashboard/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_dashboard_requires_staff(regular_client):
    response = regular_client.get("/api/v1/analytics/dashboard/")
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_dashboard_allows_staff_and_returns_real_metrics(staff_client, staff_user, user):
    movie = MovieFactory(title="Analytics Film")
    MovieInteraction.objects.create(
        user=user,
        movie=movie,
        event_type=InteractionEventType.CLICK,
    )
    log_recommendation_serve(
        algorithm="popular",
        movie_ids=[movie.id],
        cached=True,
        user=staff_user,
        surface="popular",
    )
    CollaborativeModelArtifact.objects.create(
        version="cf-test-v1",
        artifact_path="/tmp/cf",
        is_active=True,
        user_count=2,
        item_count=1,
        interaction_count=3,
        metrics={"precision_at_k": 0.2},
        hyperparameters={},
        trained_at=timezone.now(),
    )
    RecommendationEvaluationReport.objects.create(
        model_name="hybrid",
        model_version="weighted-v1",
        report_type="single",
        dataset_info={},
        configuration={},
        metrics={
            "precision_at_k": {"10": 0.12},
            "recall_at_k": {"10": 0.34},
            "ndcg_at_k": {"10": 0.21},
            "evaluated_users": 5,
        },
        sufficient_data=True,
        evaluated_at=timezone.now(),
    )

    response = staff_client.get("/api/v1/analytics/dashboard/?refresh=true")
    assert response.status_code == status.HTTP_200_OK
    payload = response.data
    assert payload["metrics"]["total_users"] >= 2
    assert payload["metrics"]["movies"] >= 1
    assert payload["metrics"]["recommendations_served"] >= 1
    assert payload["metrics"]["cache_hit_rate"] == 1.0
    assert payload["recommendation"]["by_algorithm"][0]["algorithm"] == "popular"
    assert payload["ml"]["current_model_version"] == "cf-test-v1"
    assert payload["ml"]["evaluation"]["precision_at_k"]["10"] == 0.12
    assert "notes" in payload


@pytest.mark.django_db
def test_refresh_endpoint_staff_only(regular_client, staff_client):
    denied = regular_client.post("/api/v1/analytics/refresh/")
    assert denied.status_code == status.HTTP_403_FORBIDDEN

    allowed = staff_client.post("/api/v1/analytics/refresh/")
    assert allowed.status_code == status.HTTP_200_OK
    assert AnalyticsDailySnapshot.objects.count() == 1


@pytest.mark.django_db
def test_recommendation_endpoints_write_serve_events(api_client, user):
    MovieFactory(title="Served Film", popularity=99, vote_average=9)
    response = api_client.get("/api/v1/recommendations/popular/?limit=5")
    assert response.status_code == status.HTTP_200_OK
    assert "serve_id" in response.data
    assert RecommendationServeEvent.objects.filter(algorithm="popular").exists()


@pytest.mark.django_db
def test_aggregation_does_not_fabricate_rates_without_denominator(db):
    snapshot = compute_daily_snapshot()
    assert snapshot.metrics["recommendation_ctr"] is None
    assert snapshot.metrics["cache_hit_rate"] is None
    payload = get_dashboard_payload(days=7)
    assert payload["metrics"]["recommendation_ctr"] is None
