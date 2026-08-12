from django.contrib import admin

from apps.experiments.models import Experiment, ExperimentAssignment


@admin.register(Experiment)
class ExperimentAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "status",
        "control_model",
        "treatment_model",
        "traffic_percentage",
        "start_date",
        "end_date",
    )
    list_filter = ("status",)
    search_fields = ("name", "description")


@admin.register(ExperimentAssignment)
class ExperimentAssignmentAdmin(admin.ModelAdmin):
    list_display = ("experiment", "user", "variant", "model_key", "assigned_at")
    list_filter = ("variant", "model_key")
    search_fields = ("experiment__name", "user__email")
