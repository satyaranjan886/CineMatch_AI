from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.throttles import InteractionThrottle
from apps.interactions.models import WatchHistory, Watchlist
from apps.interactions.serializers import (
    ContinueWatchingSerializer,
    InteractionCreateSerializer,
    MovieInteractionSerializer,
    RatingSerializer,
    RatingWriteSerializer,
    WatchHistorySerializer,
    WatchlistSerializer,
)
from apps.interactions.services.continue_watching import get_continue_watching
from apps.interactions.services.interactions import (
    add_like,
    add_to_watchlist,
    get_user_rating,
    remove_from_watchlist,
    remove_like,
    set_rating,
)
from apps.movies.models import Movie


class InteractionCreateView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [InteractionThrottle]

    @extend_schema(request=InteractionCreateSerializer, responses={201: MovieInteractionSerializer})
    def post(self, request):
        serializer = InteractionCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        interaction = serializer.save()
        status_code = (
            status.HTTP_201_CREATED
            if serializer.context.get("interaction_created", True)
            else status.HTTP_200_OK
        )
        return Response(MovieInteractionSerializer(interaction).data, status=status_code)


class WatchHistoryListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = WatchHistorySerializer

    def get_queryset(self):
        return (
            WatchHistory.objects.filter(user=self.request.user)
            .select_related("movie")
            .prefetch_related("movie__movie_genres__genre")
            .order_by("-last_watched_at")
        )


class WatchHistoryDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        deleted, _ = WatchHistory.objects.filter(user=request.user, pk=pk).delete()
        if not deleted:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class WatchlistListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = WatchlistSerializer

    def get_queryset(self):
        return (
            Watchlist.objects.filter(user=self.request.user)
            .select_related("movie")
            .prefetch_related("movie__movie_genres__genre")
            .order_by("-created_at")
        )


class ContinueWatchingView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: ContinueWatchingSerializer(many=True)})
    def get(self, request):
        entries = get_continue_watching(request.user)
        data = [ContinueWatchingSerializer(entry).data for entry in entries]
        return Response(data)


class MovieRatingView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_movie(self, movie_id):
        try:
            return Movie.objects.get(pk=movie_id)
        except Movie.DoesNotExist:
            return None

    @extend_schema(responses={200: RatingSerializer})
    def get(self, request, movie_id):
        movie = self._get_movie(movie_id)
        if movie is None:
            return Response({"detail": "Movie not found."}, status=status.HTTP_404_NOT_FOUND)
        rating = get_user_rating(user=request.user, movie=movie)
        if rating is None:
            return Response({"detail": "Rating not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(RatingSerializer(rating).data)

    @extend_schema(request=RatingWriteSerializer, responses={200: RatingSerializer})
    def post(self, request, movie_id):
        movie = self._get_movie(movie_id)
        if movie is None:
            return Response({"detail": "Movie not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = RatingWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rating, created = set_rating(
            user=request.user,
            movie=movie,
            score=serializer.validated_data["score"],
        )
        code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(RatingSerializer(rating).data, status=code)


class MovieLikeView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_movie(self, movie_id):
        try:
            return Movie.objects.get(pk=movie_id)
        except Movie.DoesNotExist:
            return None

    @extend_schema(responses={201: dict})
    def post(self, request, movie_id):
        movie = self._get_movie(movie_id)
        if movie is None:
            return Response({"detail": "Movie not found."}, status=status.HTTP_404_NOT_FOUND)
        _, created = add_like(user=request.user, movie=movie)
        code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response({"status": "liked"}, status=code)

    def delete(self, request, movie_id):
        movie = self._get_movie(movie_id)
        if movie is None:
            return Response({"detail": "Movie not found."}, status=status.HTTP_404_NOT_FOUND)
        if not remove_like(user=request.user, movie=movie):
            return Response({"detail": "Like not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MovieWatchlistView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_movie(self, movie_id):
        try:
            return Movie.objects.get(pk=movie_id)
        except Movie.DoesNotExist:
            return None

    @extend_schema(responses={201: dict})
    def post(self, request, movie_id):
        movie = self._get_movie(movie_id)
        if movie is None:
            return Response({"detail": "Movie not found."}, status=status.HTTP_404_NOT_FOUND)
        _, created = add_to_watchlist(user=request.user, movie=movie)
        code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response({"status": "watchlisted"}, status=code)

    def delete(self, request, movie_id):
        movie = self._get_movie(movie_id)
        if movie is None:
            return Response({"detail": "Movie not found."}, status=status.HTTP_404_NOT_FOUND)
        if not remove_from_watchlist(user=request.user, movie=movie):
            return Response(
                {"detail": "Watchlist item not found."}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
