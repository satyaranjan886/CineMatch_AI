import uuid

import pytest
from rest_framework import status

from apps.interactions.models import Like, MovieInteraction, Rating, WatchHistory, Watchlist
from tests.movies.factories import MovieFactory


@pytest.fixture
def movie(db):
    return MovieFactory(title="Interaction Film")


@pytest.fixture
def other_user(db):
    from apps.accounts.models import User

    return User.objects.create_user(email="other@example.com", password="test-pass-123")


@pytest.mark.django_db
def test_record_watch_progress_interaction(auth_client, user, movie):
    response = auth_client.post(
        "/api/v1/interactions/",
        {
            "movie_id": str(movie.id),
            "event_type": "watch_progress",
            "watch_percentage": 75,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert MovieInteraction.objects.filter(user=user, movie=movie).count() == 1
    history = WatchHistory.objects.get(user=user, movie=movie)
    assert history.watch_percentage == 75


@pytest.mark.django_db
def test_interaction_idempotency(auth_client, user, movie):
    payload = {
        "movie_id": str(movie.id),
        "event_type": "click",
        "idempotency_key": "click-abc",
    }
    first = auth_client.post("/api/v1/interactions/", payload, format="json")
    second = auth_client.post("/api/v1/interactions/", payload, format="json")

    assert first.status_code == status.HTTP_201_CREATED
    assert second.status_code == status.HTTP_200_OK
    assert MovieInteraction.objects.filter(user=user, idempotency_key="click-abc").count() == 1


@pytest.mark.django_db
def test_interaction_rejects_invalid_movie(auth_client):
    response = auth_client.post(
        "/api/v1/interactions/",
        {
            "movie_id": str(uuid.uuid4()),
            "event_type": "click",
        },
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "movie_id" in response.data


@pytest.mark.django_db
def test_interaction_rejects_invalid_watch_percentage(auth_client, movie):
    response = auth_client.post(
        "/api/v1/interactions/",
        {
            "movie_id": str(movie.id),
            "event_type": "watch_progress",
            "watch_percentage": 150,
        },
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_interaction_requires_auth(api_client, movie):
    response = api_client.post(
        "/api/v1/interactions/",
        {"movie_id": str(movie.id), "event_type": "click"},
        format="json",
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_search_interaction_without_movie(auth_client, user):
    response = auth_client.post(
        "/api/v1/interactions/",
        {"event_type": "search", "metadata": {"query": "neo noir"}},
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert MovieInteraction.objects.filter(user=user, event_type="search").exists()


@pytest.mark.django_db
def test_watch_history_list_and_delete(auth_client, user, movie):
    auth_client.post(
        "/api/v1/interactions/",
        {"movie_id": str(movie.id), "event_type": "watch_progress", "watch_percentage": 40},
        format="json",
    )
    history = WatchHistory.objects.get(user=user, movie=movie)

    list_response = auth_client.get("/api/v1/users/me/history/")
    assert list_response.status_code == status.HTTP_200_OK
    assert list_response.data["count"] == 1

    delete_response = auth_client.delete(f"/api/v1/users/me/history/{history.id}/")
    assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    assert WatchHistory.objects.filter(user=user).count() == 0


@pytest.mark.django_db
def test_history_delete_enforces_ownership(auth_client, user, movie, other_user):
    history = WatchHistory.objects.create(user=other_user, movie=movie, watch_percentage=10)
    response = auth_client.delete(f"/api/v1/users/me/history/{history.id}/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_rating_create_and_get(auth_client, user, movie):
    create = auth_client.post(
        f"/api/v1/movies/{movie.id}/rating/",
        {"score": "8.5"},
        format="json",
    )
    assert create.status_code == status.HTTP_201_CREATED
    assert Rating.objects.filter(user=user, movie=movie, score=8.5).exists()

    get = auth_client.get(f"/api/v1/movies/{movie.id}/rating/")
    assert get.status_code == status.HTTP_200_OK
    assert float(get.data["score"]) == 8.5


@pytest.mark.django_db
def test_rating_invalid_movie(auth_client):
    response = auth_client.post(
        f"/api/v1/movies/{uuid.uuid4()}/rating/",
        {"score": "7.0"},
        format="json",
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_like_duplicate_is_idempotent(auth_client, user, movie):
    first = auth_client.post(f"/api/v1/movies/{movie.id}/like/")
    second = auth_client.post(f"/api/v1/movies/{movie.id}/like/")

    assert first.status_code == status.HTTP_201_CREATED
    assert second.status_code == status.HTTP_200_OK
    assert Like.objects.filter(user=user, movie=movie).count() == 1


@pytest.mark.django_db
def test_like_delete(auth_client, user, movie):
    auth_client.post(f"/api/v1/movies/{movie.id}/like/")
    response = auth_client.delete(f"/api/v1/movies/{movie.id}/like/")
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert Like.objects.filter(user=user, movie=movie).count() == 0


@pytest.mark.django_db
def test_watchlist_duplicate_is_idempotent(auth_client, user, movie):
    first = auth_client.post(f"/api/v1/movies/{movie.id}/watchlist/")
    second = auth_client.post(f"/api/v1/movies/{movie.id}/watchlist/")

    assert first.status_code == status.HTTP_201_CREATED
    assert second.status_code == status.HTTP_200_OK
    assert Watchlist.objects.filter(user=user, movie=movie).count() == 1


@pytest.mark.django_db
def test_watchlist_list(auth_client, user, movie):
    auth_client.post(f"/api/v1/movies/{movie.id}/watchlist/")
    response = auth_client.get("/api/v1/users/me/watchlist/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 1


@pytest.mark.django_db
def test_continue_watching_service(auth_client, user, movie):
    auth_client.post(
        "/api/v1/interactions/",
        {"movie_id": str(movie.id), "event_type": "watch_progress", "watch_percentage": 55},
        format="json",
    )
    response = auth_client.get("/api/v1/users/me/continue-watching/")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1
    assert response.data[0]["watch_percentage"] == 55


@pytest.mark.django_db
def test_completed_movie_excluded_from_continue_watching(auth_client, movie):
    auth_client.post(
        "/api/v1/interactions/",
        {"movie_id": str(movie.id), "event_type": "watch_complete", "watch_percentage": 100},
        format="json",
    )
    response = auth_client.get("/api/v1/users/me/continue-watching/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data == []
