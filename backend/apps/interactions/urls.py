from django.urls import path

from apps.interactions.views import (
    ContinueWatchingView,
    InteractionCreateView,
    MovieLikeView,
    MovieRatingView,
    MovieWatchlistView,
    WatchHistoryDetailView,
    WatchHistoryListView,
    WatchlistListView,
)

urlpatterns = [
    path("interactions/", InteractionCreateView.as_view(), name="interaction-create"),
    path("users/me/history/", WatchHistoryListView.as_view(), name="user-history-list"),
    path(
        "users/me/history/<uuid:pk>/", WatchHistoryDetailView.as_view(), name="user-history-detail"
    ),
    path("users/me/watchlist/", WatchlistListView.as_view(), name="user-watchlist-list"),
    path(
        "users/me/continue-watching/", ContinueWatchingView.as_view(), name="user-continue-watching"
    ),
    path("movies/<uuid:movie_id>/rating/", MovieRatingView.as_view(), name="movie-rating"),
    path("movies/<uuid:movie_id>/like/", MovieLikeView.as_view(), name="movie-like"),
    path("movies/<uuid:movie_id>/watchlist/", MovieWatchlistView.as_view(), name="movie-watchlist"),
]
