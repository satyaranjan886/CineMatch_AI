"""Offline analytics aggregation from live tables into daily snapshots."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from statistics import mean

from django.contrib.auth import get_user_model
from django.db.models import Count
from django.utils import timezone

from apps.analytics.models import AnalyticsDailySnapshot, RecommendationServeEvent
from apps.interactions.models import InteractionEventType, MovieInteraction, WatchHistory
from apps.movies.models import Movie, MovieGenre
from apps.recommendations.models import CollaborativeModelArtifact, RecommendationEvaluationReport

User = get_user_model()

SESSION_GAP = timedelta(minutes=30)
ACTIVE_WINDOW_DAYS = 30


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    start = timezone.make_aware(datetime.combine(day, datetime.min.time()))
    end = start + timedelta(days=1)
    return start, end


def _session_durations_seconds(day: date) -> list[float]:
    start, end = _day_bounds(day)
    events = list(
        MovieInteraction.objects.filter(created_at__gte=start, created_at__lt=end)
        .order_by("user_id", "created_at")
        .values_list("user_id", "created_at")
    )
    durations: list[float] = []
    sessions: dict = defaultdict(list)
    for user_id, created_at in events:
        sessions[user_id].append(created_at)

    for stamps in sessions.values():
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


def _unique_active_users(since: datetime) -> int:
    return (
        MovieInteraction.objects.filter(created_at__gte=since).values("user_id").distinct().count()
    )


def _recommendation_metrics(day: date) -> dict:
    start, end = _day_bounds(day)
    serves = RecommendationServeEvent.objects.filter(served_at__gte=start, served_at__lt=end)
    served_count = serves.count()
    cache_hits = serves.filter(cached=True).count()
    by_algorithm = list(serves.values("algorithm").annotate(count=Count("id")).order_by("-count"))

    movie_counter: Counter[str] = Counter()
    for movie_ids in serves.values_list("movie_ids", flat=True):
        for movie_id in movie_ids or []:
            movie_counter[str(movie_id)] += 1

    clicks = MovieInteraction.objects.filter(
        created_at__gte=start,
        created_at__lt=end,
        event_type=InteractionEventType.CLICK,
        movie_id__isnull=False,
    )
    click_count = clicks.count()
    top_clicked = list(
        clicks.values("movie_id").annotate(count=Count("id")).order_by("-count")[:10]
    )

    completions = WatchHistory.objects.filter(
        completed_at__gte=start,
        completed_at__lt=end,
    )
    completion_count = completions.count()
    top_completed = list(
        completions.values("movie_id").annotate(count=Count("id")).order_by("-count")[:10]
    )

    impressions = MovieInteraction.objects.filter(
        created_at__gte=start,
        created_at__lt=end,
        event_type=InteractionEventType.IMPRESSION,
    ).count()
    # Prefer explicit impressions; otherwise use served item exposures as denominator proxy.
    exposure_denominator = (
        impressions if impressions > 0 else sum(serves.values_list("item_count", flat=True))
    )
    ctr = (click_count / exposure_denominator) if exposure_denominator else None
    conversion = (completion_count / served_count) if served_count else None

    top_recommended = []
    for movie_id, count in movie_counter.most_common(10):
        top_recommended.append({"movie_id": movie_id, "count": count})

    return {
        "recommendations_served": served_count,
        "cache_hits": cache_hits,
        "cache_misses": served_count - cache_hits,
        "cache_hit_rate": (cache_hits / served_count) if served_count else None,
        "by_algorithm": [
            {"algorithm": row["algorithm"], "count": row["count"]} for row in by_algorithm
        ],
        "top_recommended_movies": top_recommended,
        "top_clicked_recommendations": [
            {"movie_id": str(row["movie_id"]), "count": row["count"]} for row in top_clicked
        ],
        "top_completed_recommendations": [
            {"movie_id": str(row["movie_id"]), "count": row["count"]} for row in top_completed
        ],
        "recommendation_ctr": ctr,
        "recommendation_conversion": conversion,
        "clicks": click_count,
        "completions": completion_count,
        "impressions": impressions,
        "exposures": exposure_denominator,
    }


def _user_metrics(day: date) -> dict:
    start, end = _day_bounds(day)
    dau = (
        MovieInteraction.objects.filter(created_at__gte=start, created_at__lt=end)
        .values("user_id")
        .distinct()
        .count()
    )
    wau = _unique_active_users(end - timedelta(days=7))
    mau = _unique_active_users(end - timedelta(days=30))
    new_users = User.objects.filter(date_joined__gte=start, date_joined__lt=end).count()
    returning_users = (
        MovieInteraction.objects.filter(created_at__gte=start, created_at__lt=end)
        .exclude(user__date_joined__gte=start, user__date_joined__lt=end)
        .values("user_id")
        .distinct()
        .count()
    )

    genre_rows = (
        MovieGenre.objects.filter(
            movie__interactions__created_at__gte=start,
            movie__interactions__created_at__lt=end,
        )
        .values("genre__name")
        .annotate(count=Count("id"))
        .order_by("-count")[:10]
    )
    return {
        "dau": dau,
        "wau": wau,
        "mau": mau,
        "new_users": new_users,
        "returning_users": returning_users,
        "top_genres": [
            {"genre": row["genre__name"], "count": row["count"]}
            for row in genre_rows
            if row["genre__name"]
        ],
    }


def _platform_metrics(day: date, *, recommendation: dict | None = None) -> dict:
    start, end = _day_bounds(day)
    total_users = User.objects.count()
    active_users = _unique_active_users(timezone.now() - timedelta(days=ACTIVE_WINDOW_DAYS))
    movies = Movie.objects.count()
    interactions = MovieInteraction.objects.count()
    interactions_today = MovieInteraction.objects.filter(
        created_at__gte=start, created_at__lt=end
    ).count()

    completed = WatchHistory.objects.filter(completed_at__isnull=False).count()
    started = WatchHistory.objects.filter(watch_percentage__gt=0).count()
    watch_completion = (completed / started) if started else None

    durations = _session_durations_seconds(day)
    avg_session = mean(durations) if durations else None

    recommendation = recommendation if recommendation is not None else _recommendation_metrics(day)
    return {
        "total_users": total_users,
        "active_users": active_users,
        "movies": movies,
        "interactions": interactions,
        "interactions_today": interactions_today,
        "recommendations_served": recommendation["recommendations_served"],
        "recommendation_ctr": recommendation["recommendation_ctr"],
        "watch_completion": watch_completion,
        "average_session_duration_seconds": avg_session,
        "cache_hit_rate": recommendation["cache_hit_rate"],
    }


def _ml_metrics() -> dict:
    artifact = CollaborativeModelArtifact.objects.filter(is_active=True).first()
    latest_eval = (
        RecommendationEvaluationReport.objects.filter(sufficient_data=True)
        .exclude(report_type="comparison")
        .order_by("-evaluated_at")
        .first()
    )
    comparison = (
        RecommendationEvaluationReport.objects.filter(report_type="comparison")
        .order_by("-evaluated_at")
        .first()
    )

    eval_metrics = {}
    if latest_eval is not None:
        raw = latest_eval.metrics or {}
        eval_metrics = {
            "model_name": latest_eval.model_name,
            "model_version": latest_eval.model_version,
            "evaluated_at": latest_eval.evaluated_at.isoformat(),
            "precision_at_k": raw.get("precision_at_k", {}),
            "recall_at_k": raw.get("recall_at_k", {}),
            "ndcg_at_k": raw.get("ndcg_at_k", {}),
            "map_at_k": raw.get("map_at_k", {}),
            "hit_rate_at_k": raw.get("hit_rate_at_k", {}),
            "evaluated_users": raw.get("evaluated_users"),
        }

    return {
        "current_model_version": artifact.version if artifact else None,
        "training_date": artifact.trained_at.isoformat() if artifact else None,
        "training_metrics": artifact.metrics if artifact else {},
        "evaluation": eval_metrics,
        "latest_comparison_at": comparison.evaluated_at.isoformat() if comparison else None,
    }


def compute_daily_snapshot(day: date | None = None) -> AnalyticsDailySnapshot:
    day = day or timezone.localdate()
    now = timezone.now()
    recommendation = _recommendation_metrics(day)
    metrics = _platform_metrics(day, recommendation=recommendation)
    users = _user_metrics(day)
    ml = _ml_metrics()

    snapshot, _ = AnalyticsDailySnapshot.objects.update_or_create(
        date=day,
        defaults={
            "metrics": metrics,
            "recommendation": recommendation,
            "users": users,
            "ml": ml,
            "computed_at": now,
        },
    )
    return snapshot


def get_dashboard_payload(*, days: int = 14) -> dict:
    """
    Prefer the latest precomputed snapshot for headline metrics.
    Time series come from recent snapshots only (no expensive live scans).
    """
    latest = AnalyticsDailySnapshot.objects.order_by("-date").first()
    if latest is None:
        latest = compute_daily_snapshot()

    since = latest.date - timedelta(days=max(days - 1, 0))
    history = list(
        AnalyticsDailySnapshot.objects.filter(date__gte=since, date__lte=latest.date).order_by(
            "date"
        )
    )

    movie_ids = set()
    for snap in [latest]:
        for bucket in (
            snap.recommendation.get("top_recommended_movies", []),
            snap.recommendation.get("top_clicked_recommendations", []),
            snap.recommendation.get("top_completed_recommendations", []),
        ):
            for row in bucket:
                if row.get("movie_id"):
                    movie_ids.add(row["movie_id"])

    titles = {
        str(movie.id): movie.title
        for movie in Movie.objects.filter(id__in=movie_ids).only("id", "title")
    }

    def enrich(rows: list[dict]) -> list[dict]:
        enriched = []
        for row in rows:
            movie_id = str(row.get("movie_id", ""))
            enriched.append(
                {
                    **row,
                    "movie_id": movie_id,
                    "title": titles.get(movie_id, "Unknown title"),
                }
            )
        return enriched

    recommendation = dict(latest.recommendation)
    recommendation["top_recommended_movies"] = enrich(
        recommendation.get("top_recommended_movies", [])
    )
    recommendation["top_clicked_recommendations"] = enrich(
        recommendation.get("top_clicked_recommendations", [])
    )
    recommendation["top_completed_recommendations"] = enrich(
        recommendation.get("top_completed_recommendations", [])
    )

    return {
        "as_of": latest.date.isoformat(),
        "computed_at": latest.computed_at.isoformat(),
        "sufficient_data": True,
        "metrics": latest.metrics,
        "recommendation": recommendation,
        "users": latest.users,
        "ml": latest.ml,
        "timeseries": [
            {
                "date": snap.date.isoformat(),
                "dau": snap.users.get("dau"),
                "recommendations_served": snap.metrics.get("recommendations_served"),
                "recommendation_ctr": snap.metrics.get("recommendation_ctr"),
                "cache_hit_rate": snap.metrics.get("cache_hit_rate"),
                "interactions_today": snap.metrics.get("interactions_today"),
                "new_users": snap.users.get("new_users"),
            }
            for snap in history
        ],
        "notes": (
            "Metrics are computed from database events and precomputed daily snapshots. "
            "Null rates mean no denominator events were recorded yet."
        ),
    }
