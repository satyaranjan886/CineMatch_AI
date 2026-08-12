from django.db.models import Count
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.movies.cache import get_cached_movie_detail, set_cached_movie_detail
from apps.movies.filters import GenreFilter, MovieFilter
from apps.movies.models import Genre, Movie
from apps.movies.serializers import (
    GenreDetailSerializer,
    GenreSerializer,
    MovieDetailSerializer,
    MovieListSerializer,
    SimilarMovieSerializer,
)
from apps.movies.services.similarity import get_similar_movies


@extend_schema_view(
    list=extend_schema(summary="List movies"),
    retrieve=extend_schema(summary="Retrieve a movie"),
)
class MovieViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_class = MovieFilter
    search_fields = ["title", "original_title", "overview", "tagline"]
    ordering_fields = [
        "title",
        "release_date",
        "popularity",
        "vote_average",
        "vote_count",
        "created_at",
    ]
    ordering = ["-popularity", "title"]

    def get_queryset(self):
        queryset = Movie.objects.all()
        if self.action == "list":
            return queryset.prefetch_related("movie_genres__genre")
        if self.action in {"retrieve", "similar"}:
            return queryset.with_catalog_relations()
        return queryset

    def get_serializer_class(self):
        if self.action == "retrieve":
            return MovieDetailSerializer
        return MovieListSerializer

    def retrieve(self, request, *args, **kwargs):
        movie_id = kwargs.get("pk")
        cached = get_cached_movie_detail(movie_id)
        if cached is not None:
            return Response(cached)

        instance = self.get_object()
        serializer = self.get_serializer(instance)
        payload = serializer.data
        set_cached_movie_detail(instance.id, payload)
        return Response(payload)

    @extend_schema(
        summary="Similar movies",
        description=(
            "Returns content-based similar titles using TF-IDF cosine similarity over "
            "normalized movie metadata. Authenticated users exclude watched titles."
        ),
        responses=SimilarMovieSerializer(many=True),
    )
    @action(detail=True, methods=["get"], url_path="similar")
    def similar(self, request, pk=None):
        movie = self.get_object()
        user = request.user if request.user.is_authenticated else None
        similar = get_similar_movies(movie.id, limit=12, user=user)
        payload = [
            {
                **SimilarMovieSerializer(item.movie, context=self.get_serializer_context()).data,
                "similarity_score": round(item.score, 6),
            }
            for item in similar
        ]
        return Response(payload)


@extend_schema_view(
    list=extend_schema(summary="List genres"),
    retrieve=extend_schema(summary="Retrieve a genre"),
)
class GenreViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    queryset = Genre.objects.all()
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = GenreFilter
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        queryset = Genre.objects.all()
        if self.action == "retrieve":
            return queryset.annotate(movie_count=Count("movie_genres"))
        return queryset

    def get_serializer_class(self):
        if self.action == "retrieve":
            return GenreDetailSerializer
        return GenreSerializer
