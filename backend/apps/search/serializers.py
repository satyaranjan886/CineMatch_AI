from rest_framework import serializers

from apps.movies.serializers import MovieListSerializer


class SemanticSearchResultSerializer(MovieListSerializer):
    score = serializers.FloatField(read_only=True)


class SemanticSearchResponseSerializer(serializers.Serializer):
    query = serializers.CharField()
    model_name = serializers.CharField()
    model_version = serializers.CharField()
    count = serializers.IntegerField()
    results = SemanticSearchResultSerializer(many=True)
