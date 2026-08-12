from rest_framework import serializers

from apps.experiments.models import Experiment
from apps.experiments.registry import list_model_keys


class ExperimentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Experiment
        fields = (
            "id",
            "name",
            "description",
            "control_model",
            "treatment_model",
            "traffic_percentage",
            "start_date",
            "end_date",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "status", "created_at", "updated_at")

    def validate_control_model(self, value: str) -> str:
        if value not in list_model_keys():
            raise serializers.ValidationError(
                f"Unknown model key. Choose from {list_model_keys()}."
            )
        return value

    def validate_treatment_model(self, value: str) -> str:
        if value not in list_model_keys():
            raise serializers.ValidationError(
                f"Unknown model key. Choose from {list_model_keys()}."
            )
        return value


class ExperimentResultsSerializer(serializers.Serializer):
    experiment_id = serializers.UUIDField()
    experiment_name = serializers.CharField()
    status = serializers.CharField()
    control_model = serializers.CharField()
    treatment_model = serializers.CharField()
    traffic_percentage = serializers.IntegerField()
    start_date = serializers.CharField(allow_null=True)
    end_date = serializers.CharField(allow_null=True)
    variants = serializers.DictField()
    notes = serializers.CharField()
