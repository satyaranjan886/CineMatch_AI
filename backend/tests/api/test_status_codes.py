"""API status-code contract tests across auth, catalog, interactions, and staff APIs."""

from __future__ import annotations

import pytest
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.throttles import AuthLoginThrottle, SearchThrottle
from tests.movies.factories import MovieFactory


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    cache.clear()
    yield
    cache.clear()
    # Restore generous test rates after throttle assertions.
    from django.conf import settings

    AuthLoginThrottle.THROTTLE_RATES = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    SearchThrottle.THROTTLE_RATES = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]


@pytest.mark.django_db
def test_movies_list_200(api_client):
    MovieFactory(title="Status Movie")
    response = api_client.get("/api/v1/movies/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] >= 1


@pytest.mark.django_db
def test_movie_detail_200_and_404(api_client):
    movie = MovieFactory(title="Detail Status")
    ok = api_client.get(f"/api/v1/movies/{movie.id}/")
    assert ok.status_code == status.HTTP_200_OK
    missing = api_client.get("/api/v1/movies/00000000-0000-0000-0000-000000000099/")
    assert missing.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_register_201_and_400(api_client, register_payload):
    created = api_client.post("/api/v1/auth/register/", register_payload, format="json")
    assert created.status_code == status.HTTP_201_CREATED
    assert "access" in created.data

    weak = {**register_payload, "email": "weak@example.com", "password": "123"}
    bad = api_client.post("/api/v1/auth/register/", weak, format="json")
    assert bad.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_login_200_and_401(api_client, user):
    ok = api_client.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": "test-pass-123"},
        format="json",
    )
    assert ok.status_code == status.HTTP_200_OK

    unauthorized = api_client.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": "wrong-password"},
        format="json",
    )
    assert unauthorized.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_me_401_without_auth(api_client):
    response = api_client.get("/api/v1/auth/me/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_interaction_201_and_400(auth_client, user):
    movie = MovieFactory(title="Interaction Status")
    created = auth_client.post(
        "/api/v1/interactions/",
        {"movie_id": str(movie.id), "event_type": "like"},
        format="json",
    )
    assert created.status_code in {status.HTTP_201_CREATED, status.HTTP_200_OK}

    invalid = auth_client.post(
        "/api/v1/interactions/",
        {"event_type": "like"},
        format="json",
    )
    assert invalid.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_home_recommendations_401(api_client):
    response = api_client.get("/api/v1/recommendations/home/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_analytics_403_for_non_staff(auth_client):
    response = auth_client.get("/api/v1/analytics/dashboard/")
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_experiments_401_and_403(user):
    anon = APIClient()
    assert anon.get("/api/v1/experiments/").status_code == status.HTTP_401_UNAUTHORIZED

    regular = APIClient()
    login = regular.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": "test-pass-123"},
        format="json",
    )
    assert login.status_code == 200
    regular.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    assert regular.get("/api/v1/experiments/").status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_experiments_404_for_staff(db):
    staff = User.objects.create_user(
        email="status-staff@example.com",
        password="test-pass-123",
        is_staff=True,
    )
    client = APIClient()
    login = client.post(
        "/api/v1/auth/login/",
        {"email": staff.email, "password": "test-pass-123"},
        format="json",
    )
    assert login.status_code == 200
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    response = client.get("/api/v1/experiments/00000000-0000-0000-0000-000000000099/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_semantic_search_400_missing_query(api_client):
    response = api_client.get("/api/v1/search/semantic/")
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_login_throttle_returns_429(api_client, user):
    AuthLoginThrottle.THROTTLE_RATES = {
        **dict(AuthLoginThrottle.THROTTLE_RATES or {}),
        "auth_login": "2/min",
    }
    cache.clear()

    payload = {"email": user.email, "password": "wrong-password"}
    first = api_client.post("/api/v1/auth/login/", payload, format="json")
    second = api_client.post("/api/v1/auth/login/", payload, format="json")
    third = api_client.post("/api/v1/auth/login/", payload, format="json")

    assert first.status_code == status.HTTP_401_UNAUTHORIZED
    assert second.status_code == status.HTTP_401_UNAUTHORIZED
    assert third.status_code == status.HTTP_429_TOO_MANY_REQUESTS


@pytest.mark.django_db
def test_search_throttle_returns_429(api_client):
    SearchThrottle.THROTTLE_RATES = {
        **dict(SearchThrottle.THROTTLE_RATES or {}),
        "search": "1/min",
    }
    cache.clear()

    first = api_client.get("/api/v1/search/semantic/?q=space")
    second = api_client.get("/api/v1/search/semantic/?q=space")
    assert first.status_code == status.HTTP_200_OK
    assert second.status_code == status.HTTP_429_TOO_MANY_REQUESTS
