"""Experiment lifecycle transitions."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.experiments.models import Experiment, ExperimentStatus
from apps.experiments.registry import get_model_definition


def validate_models(control_model: str, treatment_model: str) -> None:
    get_model_definition(control_model)
    get_model_definition(treatment_model)


def start_experiment(experiment: Experiment) -> Experiment:
    if experiment.status not in {ExperimentStatus.DRAFT, ExperimentStatus.PAUSED}:
        raise ValidationError("Only draft or paused experiments can be started.")
    validate_models(experiment.control_model, experiment.treatment_model)

    running = Experiment.objects.filter(status=ExperimentStatus.RUNNING).exclude(pk=experiment.pk)
    if running.exists():
        raise ValidationError("Another experiment is already running. Stop it first.")

    experiment.status = ExperimentStatus.RUNNING
    if experiment.start_date is None:
        experiment.start_date = timezone.now()
    experiment.save(update_fields=["status", "start_date", "updated_at"])
    return experiment


def pause_experiment(experiment: Experiment) -> Experiment:
    if experiment.status != ExperimentStatus.RUNNING:
        raise ValidationError("Only running experiments can be paused.")
    experiment.status = ExperimentStatus.PAUSED
    experiment.save(update_fields=["status", "updated_at"])
    return experiment


def stop_experiment(experiment: Experiment) -> Experiment:
    if experiment.status not in {ExperimentStatus.RUNNING, ExperimentStatus.PAUSED}:
        raise ValidationError("Only running or paused experiments can be stopped.")
    experiment.status = ExperimentStatus.STOPPED
    experiment.end_date = timezone.now()
    experiment.save(update_fields=["status", "end_date", "updated_at"])
    return experiment
