import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(
        email="viewer@example.com",
        password="test-pass-123",
        first_name="Ada",
    )


@pytest.fixture
def auth_client(api_client, user) -> APIClient:
    response = api_client.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": "test-pass-123"},
        format="json",
    )
    assert response.status_code == 200, response.data
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    return api_client


@pytest.fixture
def register_payload():
    return {
        "email": "newuser@example.com",
        "password": "Str0ngPass!",
        "first_name": "New",
        "last_name": "User",
        "display_name": "Newbie",
    }
