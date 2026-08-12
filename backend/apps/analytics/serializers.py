from rest_framework import serializers


class AnalyticsDashboardSerializer(serializers.Serializer):
    as_of = serializers.DateField()
    computed_at = serializers.DateTimeField()
    sufficient_data = serializers.BooleanField()
    metrics = serializers.DictField()
    recommendation = serializers.DictField()
    users = serializers.DictField()
    ml = serializers.DictField()
    timeseries = serializers.ListField(child=serializers.DictField())
    notes = serializers.CharField()
