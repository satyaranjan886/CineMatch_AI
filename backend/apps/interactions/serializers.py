from decimal import Decimal

from rest_framework import serializers

from apps.interactions.models import (
    InteractionEventType,
    MovieInteraction,
    Rating,
    WatchHistory,
    Watchlist,
)
from apps.interactions.services.interactions import InteractionValidationError, record_interaction
from apps.movies.models import Movie
from apps.movies.serializers import MovieListSerializer


class InteractionCreateSerializer(serializers.Serializer):
    movie_id = serializers.UUIDField(required=False, allow_null=True)
    event_type = serializers.ChoiceField(choices=InteractionEventType.choices)
    watch_percentage = serializers.IntegerField(required=False, min_value=0, max_value=100)
    metadata = serializers.JSONField(required=False, default=dict)
    idempotency_key = serializers.CharField(required=False, allow_blank=True, max_length=128)

    def validate_movie_id(self, value):
        if value is None:
            return None
        if not Movie.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Movie not found.")
        return value

    def validate_metadata(self, value):
        import json

        from django.conf import settings

        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("Metadata must be a JSON object.")
        encoded = json.dumps(value, default=str)
        max_bytes = getattr(settings, "INTERACTION_METADATA_MAX_BYTES", 4096)
        if len(encoded.encode("utf-8")) > max_bytes:
            raise serializers.ValidationError(
                f"Metadata exceeds maximum size of {max_bytes} bytes."
            )
        return value

    def validate(self, attrs):
        event_type = attrs["event_type"]
        movie_id = attrs.get("movie_id")
        if event_type != InteractionEventType.SEARCH and movie_id is None:
            raise serializers.ValidationError(
                {"movie_id": "This field is required for this event type."}
            )
        return attrs

    def create(self, validated_data):
        user = self.context["request"].user
        movie = None
        movie_id = validated_data.get("movie_id")
        if movie_id is not None:
            movie = Movie.objects.get(pk=movie_id)

        try:
            result = record_interaction(
                user=user,
                event_type=validated_data["event_type"],
                movie=movie,
                watch_percentage=validated_data.get("watch_percentage"),
                metadata=validated_data.get("metadata") or {},
                idempotency_key=validated_data.get("idempotency_key", ""),
            )
        except InteractionValidationError as exc:
            if exc.field:
                raise serializers.ValidationError({exc.field: exc.message}) from exc
            raise serializers.ValidationError({"detail": exc.message}) from exc

        self.context["interaction_created"] = result.created
        return result.interaction


class MovieInteractionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MovieInteraction
        fields = (
            "id",
            "movie_id",
            "event_type",
            "watch_percentage",
            "metadata",
            "idempotency_key",
            "created_at",
        )
        read_only_fields = fields


class WatchHistorySerializer(serializers.ModelSerializer):
    movie = MovieListSerializer(read_only=True)

    class Meta:
        model = WatchHistory
        fields = (
            "id",
            "movie",
            "watch_percentage",
            "last_watched_at",
            "completed_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class RatingWriteSerializer(serializers.Serializer):
    score = serializers.DecimalField(
        max_digits=3,
        decimal_places=1,
        min_value=Decimal("0.5"),
        max_value=Decimal("10.0"),
    )


class RatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rating
        fields = ("id", "score", "created_at", "updated_at")
        read_only_fields = fields


class WatchlistSerializer(serializers.ModelSerializer):
    movie = MovieListSerializer(read_only=True)

    class Meta:
        model = Watchlist
        fields = ("id", "movie", "created_at", "updated_at")
        read_only_fields = fields


class ContinueWatchingSerializer(serializers.Serializer):
    id = serializers.UUIDField(source="movie.id")
    title = serializers.CharField(source="movie.title")
    poster_url = serializers.URLField(source="movie.poster_url")
    watch_percentage = serializers.IntegerField()
    last_watched_at = serializers.DateTimeField()

    def to_representation(self, instance: WatchHistory):
        return {
            "id": str(instance.movie_id),
            "title": instance.movie.title,
            "poster_url": instance.movie.poster_url,
            "watch_percentage": instance.watch_percentage,
            "last_watched_at": instance.last_watched_at,
        }
