"""A/B experiment models for recommendation serving."""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.common.models import TimeStampedModel, UUIDModel


class ExperimentStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    RUNNING = "running", "Running"
    PAUSED = "paused", "Paused"
    STOPPED = "stopped", "Stopped"
    COMPLETED = "completed", "Completed"


class ExperimentVariant(models.TextChoices):
    CONTROL = "control", "Control"
    TREATMENT = "treatment", "Treatment"


class Experiment(UUIDModel, TimeStampedModel):
    name = models.CharField(max_length=128, unique=True, db_index=True)
    description = models.TextField(blank=True)
    control_model = models.CharField(max_length=64)
    treatment_model = models.CharField(max_length=64)
    traffic_percentage = models.PositiveSmallIntegerField(
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Percentage of eligible users assigned to treatment.",
    )
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=16,
        choices=ExperimentStatus.choices,
        default=ExperimentStatus.DRAFT,
        db_index=True,
    )

    class Meta:
        db_table = "experiments"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-start_date"], name="experiments_status_start_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.status})"

    @property
    def is_active(self) -> bool:
        if self.status != ExperimentStatus.RUNNING:
            return False
        now = timezone.now()
        if self.start_date and now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False
        return True


class ExperimentAssignment(UUIDModel, TimeStampedModel):
    experiment = models.ForeignKey(
        Experiment,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="experiment_assignments",
    )
    variant = models.CharField(max_length=16, choices=ExperimentVariant.choices, db_index=True)
    model_key = models.CharField(max_length=64)
    assigned_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "experiment_assignments"
        constraints = [
            models.UniqueConstraint(
                fields=["experiment", "user"],
                name="experiment_assignments_unique_user",
            ),
        ]
        indexes = [
            models.Index(fields=["experiment", "variant"], name="exp_assign_variant_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} → {self.experiment.name}:{self.variant}"
