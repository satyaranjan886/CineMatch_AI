"""Deterministic sticky experiment assignment."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from uuid import UUID

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.experiments.models import (
    Experiment,
    ExperimentAssignment,
    ExperimentStatus,
    ExperimentVariant,
)
from apps.experiments.registry import get_model_definition


@dataclass(frozen=True)
class ServingDecision:
    experiment: Experiment | None
    assignment: ExperimentAssignment | None
    variant: str | None
    model_key: str
    model_version: str

    @property
    def experiment_id(self) -> UUID | None:
        return self.experiment.id if self.experiment else None


def _bucket(user_id: UUID, experiment_id: UUID) -> int:
    digest = hashlib.sha256(f"{experiment_id}:{user_id}".encode()).hexdigest()
    return int(digest[:8], 16) % 100


def choose_variant(experiment: Experiment, user_id: UUID) -> str:
    bucket = _bucket(user_id, experiment.id)
    if bucket < experiment.traffic_percentage:
        return ExperimentVariant.TREATMENT
    return ExperimentVariant.CONTROL


def model_key_for_variant(experiment: Experiment, variant: str) -> str:
    if variant == ExperimentVariant.TREATMENT:
        return experiment.treatment_model
    return experiment.control_model


def get_active_experiment() -> Experiment | None:
    now = timezone.now()
    return (
        Experiment.objects.filter(status=ExperimentStatus.RUNNING)
        .filter(Q(start_date__isnull=True) | Q(start_date__lte=now))
        .filter(Q(end_date__isnull=True) | Q(end_date__gte=now))
        .order_by("-start_date", "-created_at")
        .first()
    )


@transaction.atomic
def assign_user(experiment: Experiment, user) -> ExperimentAssignment:
    existing = (
        ExperimentAssignment.objects.select_for_update()
        .filter(experiment=experiment, user=user)
        .first()
    )
    if existing is not None:
        return existing

    variant = choose_variant(experiment, user.id)
    model_key = model_key_for_variant(experiment, variant)
    return ExperimentAssignment.objects.create(
        experiment=experiment,
        user=user,
        variant=variant,
        model_key=model_key,
    )


def resolve_serving_decision(user) -> ServingDecision:
    """
    Pick the model version that should serve this user.

    Sticky assignment: once assigned, the user stays on the same variant for
    the lifetime of the experiment row.
    """
    default_key = "hybrid_v1"
    try:
        default_def = get_model_definition(default_key)
    except KeyError:
        return ServingDecision(
            experiment=None,
            assignment=None,
            variant=None,
            model_key=default_key,
            model_version=getattr(settings, "RECOMMENDATION_VERSION", "v1"),
        )

    if user is None or not getattr(user, "is_authenticated", False):
        return ServingDecision(
            experiment=None,
            assignment=None,
            variant=None,
            model_key=default_def.key,
            model_version=default_def.version,
        )

    experiment = get_active_experiment()
    if experiment is None:
        return ServingDecision(
            experiment=None,
            assignment=None,
            variant=None,
            model_key=default_def.key,
            model_version=default_def.version,
        )

    assignment = assign_user(experiment, user)
    definition = get_model_definition(assignment.model_key)
    return ServingDecision(
        experiment=experiment,
        assignment=assignment,
        variant=assignment.variant,
        model_key=assignment.model_key,
        model_version=definition.version,
    )
