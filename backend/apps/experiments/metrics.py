"""Per-variant experiment outcome metrics from live events."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from statistics import mean
from uuid import UUID

from django.db.models import Sum
from django.utils import timezone

from apps.analytics.models import RecommendationServeEvent
from apps.experiments.models import Experiment, ExperimentAssignment, ExperimentVariant
from apps.interactions.models import InteractionEventType, Like, MovieInteraction, WatchHistory

SESSION_GAP = timedelta(minutes=30)


def _window(experiment: Experiment) -> tuple[datetime, datetime]:
    start = experiment.start_date or experiment.created_at
    end = experiment.end_date or timezone.now()
    return start, end


def _user_ids(experiment: Experiment, variant: str) -> set[UUID]:
    return set(
        ExperimentAssignment.objects.filter(experiment=experiment, variant=variant).values_list(
            "user_id", flat=True
        )
    )


def _session_durations(user_ids: set[UUID], start: datetime, end: datetime) -> list[float]:
    if not user_ids:
        return []
    events = list(
        MovieInteraction.objects.filter(
            user_id__in=user_ids,
            created_at__gte=start,
            created_at__lt=end,
        )
        .order_by("user_id", "created_at")
        .values_list("user_id", "created_at")
    )
    by_user: dict = defaultdict(list)
    for user_id, created_at in events:
        by_user[user_id].append(created_at)

    durations: list[float] = []
    for stamps in by_user.values():
        if len(stamps) < 2:
            continue
        session_start = stamps[0]
        previous = stamps[0]
        for stamp in stamps[1:]:
            if stamp - previous > SESSION_GAP:
                durations.append((previous - session_start).total_seconds())
                session_start = stamp
            previous = stamp
        durations.append((previous - session_start).total_seconds())
    return [value for value in durations if value > 0]


def _variant_metrics(experiment: Experiment, variant: str) -> dict:
    start, end = _window(experiment)
    user_ids = _user_ids(experiment, variant)
    assigned_users = len(user_ids)

    serves = RecommendationServeEvent.objects.filter(
        served_at__gte=start,
        served_at__lt=end,
        metadata__experiment_id=str(experiment.id),
        metadata__variant=variant,
    )
    served = serves.count()
    exposures = sum(serves.values_list("item_count", flat=True)) or 0

    clicks = 0
    likes = 0
    completions = 0
    watch_time_proxy = 0.0

    if user_ids:
        clicks = MovieInteraction.objects.filter(
            user_id__in=user_ids,
            created_at__gte=start,
            created_at__lt=end,
            event_type=InteractionEventType.CLICK,
        ).count()
        likes = Like.objects.filter(
            user_id__in=user_ids,
            created_at__gte=start,
            created_at__lt=end,
        ).count()
        completions = WatchHistory.objects.filter(
            user_id__in=user_ids,
            completed_at__gte=start,
            completed_at__lt=end,
        ).count()
        # Approximate watch time using progress percentage points as minutes proxy.
        watch_time_proxy = (
            WatchHistory.objects.filter(
                user_id__in=user_ids,
                last_watched_at__gte=start,
                last_watched_at__lt=end,
            ).aggregate(total=Sum("watch_percentage"))["total"]
            or 0
        )

    durations = _session_durations(user_ids, start, end)
    ctr = (clicks / exposures) if exposures else None
    return {
        "variant": variant,
        "assigned_users": assigned_users,
        "recommendations_served": served,
        "exposures": exposures,
        "clicks": clicks,
        "ctr": ctr,
        "likes": likes,
        "completions": completions,
        "watch_time": float(watch_time_proxy),
        "average_session_duration_seconds": mean(durations) if durations else None,
    }


def compute_experiment_results(experiment: Experiment) -> dict:
    control = _variant_metrics(experiment, ExperimentVariant.CONTROL)
    treatment = _variant_metrics(experiment, ExperimentVariant.TREATMENT)
    return {
        "experiment_id": str(experiment.id),
        "experiment_name": experiment.name,
        "status": experiment.status,
        "control_model": experiment.control_model,
        "treatment_model": experiment.treatment_model,
        "traffic_percentage": experiment.traffic_percentage,
        "start_date": experiment.start_date.isoformat() if experiment.start_date else None,
        "end_date": experiment.end_date.isoformat() if experiment.end_date else None,
        "variants": {
            "control": control,
            "treatment": treatment,
        },
        "notes": (
            "Metrics are computed from assignment sticky cohorts and logged recommendation serves. "
            "Null CTR means no exposures were recorded for that variant yet."
        ),
    }
