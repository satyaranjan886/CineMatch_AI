from rest_framework import serializers

from apps.movies.serializers import MovieListSerializer


class RecommendationMovieSerializer(MovieListSerializer):
    score = serializers.FloatField(read_only=True, required=False)
    reason = serializers.CharField(read_only=True, required=False)
    primary_source = serializers.CharField(read_only=True, required=False)


class RecommendationResponseSerializer(serializers.Serializer):
    strategy = serializers.CharField()
    cached = serializers.BooleanField()
    count = serializers.IntegerField()
    results = RecommendationMovieSerializer(many=True)


class HomeSectionSerializer(serializers.Serializer):
    name = serializers.CharField()
    algorithm = serializers.CharField()
    model_version = serializers.CharField()
    count = serializers.IntegerField()
    movies = RecommendationMovieSerializer(many=True)


class HomeRecommendationResponseSerializer(serializers.Serializer):
    version = serializers.CharField()
    cached = serializers.BooleanField()
    sections = HomeSectionSerializer(many=True)
