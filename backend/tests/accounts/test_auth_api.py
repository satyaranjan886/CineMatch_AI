import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Profile, UserPreference

User = get_user_model()


@pytest.mark.django_db
def test_register_creates_user_profile_and_tokens(api_client, register_payload):
    response = api_client.post("/api/v1/auth/register/", register_payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    assert "access" in response.data
    assert "refresh" not in response.data
    assert "cinematch_refresh" in response.cookies
    assert response.data["user"]["email"] == register_payload["email"]

    user = User.objects.get(email=register_payload["email"])
    assert user.check_password(register_payload["password"])
    assert user.profile.display_name == "Newbie"
    assert UserPreference.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_register_rejects_duplicate_email(api_client, register_payload, user):
    register_payload["email"] = user.email
    response = api_client.post("/api/v1/auth/register/", register_payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "email" in response.data


@pytest.mark.django_db
def test_register_rejects_weak_password(api_client, register_payload):
    register_payload["password"] = "123"
    response = api_client.post("/api/v1/auth/register/", register_payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "password" in response.data


@pytest.mark.django_db
def test_login_returns_tokens(api_client, user):
    response = api_client.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": "test-pass-123"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert "access" in response.data
    assert "refresh" not in response.data
    assert "cinematch_refresh" in response.cookies


@pytest.mark.django_db
def test_login_invalid_credentials_do_not_leak_user_existence(api_client, user):
    response = api_client.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": "wrong-password"},
        format="json",
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data["detail"] == "Invalid credentials."


@pytest.mark.django_db
def test_token_refresh(api_client, user):
    login = api_client.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": "test-pass-123"},
        format="json",
    )
    refresh = login.cookies["cinematch_refresh"].value

    response = api_client.post("/api/v1/auth/refresh/", {"refresh": refresh}, format="json")

    assert response.status_code == status.HTTP_200_OK
    assert "access" in response.data
    assert "refresh" not in response.data


@pytest.mark.django_db
def test_logout_blacklists_refresh_token(auth_client, user):
    refresh = str(RefreshToken.for_user(user))

    response = auth_client.post("/api/v1/auth/logout/", {"refresh": refresh}, format="json")

    assert response.status_code == status.HTTP_204_NO_CONTENT

    refresh_response = auth_client.post(
        "/api/v1/auth/refresh/", {"refresh": refresh}, format="json"
    )
    assert refresh_response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_me_requires_authentication(api_client):
    response = api_client.get("/api/v1/auth/me/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_me_returns_user_profile_and_preferences(auth_client, user):
    response = auth_client.get("/api/v1/auth/me/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["user"]["email"] == user.email
    assert response.data["profile"]["display_name"] == "Ada"
    assert response.data["preferences"] is not None


@pytest.mark.django_db
def test_profile_update(auth_client, user):
    response = auth_client.patch(
        "/api/v1/auth/me/profile/",
        {
            "display_name": "Updated Name",
            "avatar_url": "https://example.com/avatar.png",
            "onboarding_completed": True,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["display_name"] == "Updated Name"
    assert response.data["avatar_url"] == "https://example.com/avatar.png"
    assert response.data["onboarding_completed"] is True

    profile = Profile.objects.get(user=user, is_primary=True)
    assert profile.onboarding_completed_at is not None


@pytest.mark.django_db
def test_preferences_update(auth_client, user):
    from tests.movies.factories import ActorFactory, DirectorFactory, GenreFactory

    genre = GenreFactory(name="Horror", slug="horror")
    actor = ActorFactory(name="Test Actor")
    director = DirectorFactory(name="Test Director")

    response = auth_client.patch(
        "/api/v1/auth/me/preferences/",
        {
            "preferred_languages": ["en", "es"],
            "preferred_decades": [1990, 2000],
            "favorite_genre_ids": [str(genre.id)],
            "favorite_actor_ids": [str(actor.id)],
            "favorite_director_ids": [str(director.id)],
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["preferred_languages"] == ["en", "es"]
    assert response.data["preferred_decades"] == [1990, 2000]
    assert genre.id in response.data["favorite_genre_ids"]
    assert actor.id in response.data["favorite_actor_ids"]
    assert director.id in response.data["favorite_director_ids"]


@pytest.mark.django_db
def test_preferences_rejects_invalid_decades(auth_client):
    response = auth_client.patch(
        "/api/v1/auth/me/preferences/",
        {"preferred_decades": [1800]},
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_profile_access_denied_for_other_users(auth_client, user):
    other = User.objects.create_user(email="other@example.com", password="test-pass-123")
    assert other.profile is not None

    response = auth_client.get("/api/v1/auth/me/profile/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["display_name"] == user.profile.display_name


@pytest.mark.django_db
def test_login_sets_httponly_refresh_cookie(api_client, user):
    response = api_client.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": "test-pass-123"},
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK
    assert "cinematch_refresh" in response.cookies
    cookie = response.cookies["cinematch_refresh"]
    assert cookie["httponly"]

    # Refresh using cookie only (no body token).
    api_client.cookies["cinematch_refresh"] = cookie.value
    refresh_response = api_client.post("/api/v1/auth/refresh/", {}, format="json")
    assert refresh_response.status_code == status.HTTP_200_OK
    assert "access" in refresh_response.data
