"""Recommendation evaluation orchestration."""

from __future__ import annotations

import random
from datetime import datetime

from django.conf import settings
from django.utils import timezone

from ml.evaluation.adapters import BaseEvaluationRecommender, get_recommender
from ml.evaluation.dataset import TimedInteractionLoader
from ml.evaluation.metrics import compute_metric_snapshot
from ml.evaluation.split import (
    DEFAULT_MIN_INTERACTIONS,
    assert_no_future_in_train,
    temporal_cutoff_split,
    temporal_leave_one_out,
)
from ml.evaluation.types import (
    ComparisonReport,
    EvaluationFold,
    MetricSnapshot,
    ModelEvaluationResult,
)


def _default_k_values() -> list[int]:
    values = [int(v) for v in getattr(settings, "EVAL_K_VALUES", [5, 10, 20])]
    # Required headline metrics include @5 and @10.
    for required in (5, 10):
        if required not in values:
            values.append(required)
    return sorted(set(values))


def _minimum_users() -> int:
    return int(getattr(settings, "EVAL_MIN_USERS", 5))


def _minimum_test_interactions() -> int:
    return int(getattr(settings, "EVAL_MIN_TEST_INTERACTIONS", 10))


def _minimum_user_interactions() -> int:
    return int(getattr(settings, "EVAL_MIN_INTERACTIONS", DEFAULT_MIN_INTERACTIONS))


def _default_seed() -> int:
    return int(getattr(settings, "EVAL_RANDOM_SEED", getattr(settings, "CF_ALS_RANDOM_STATE", 42)))


def _build_fold(
    *,
    split: str,
    cutoff: datetime | None = None,
    min_interactions: int | None = None,
) -> tuple[EvaluationFold, dict]:
    interactions = TimedInteractionLoader().load()
    summary = TimedInteractionLoader.dataset_summary(interactions)
    min_interactions = (
        min_interactions if min_interactions is not None else _minimum_user_interactions()
    )
    if split == "temporal_cutoff":
        if cutoff is None:
            raise ValueError("cutoff is required for temporal_cutoff split")
        fold = temporal_cutoff_split(interactions, cutoff, min_interactions=min_interactions)
    else:
        fold = temporal_leave_one_out(interactions, min_interactions=min_interactions)

    # Fail closed in evaluation if split invariants are violated.
    assert_no_future_in_train(fold)

    summary["split_strategy"] = fold.split_strategy
    summary["train_interactions"] = len(fold.train)
    summary["test_interactions"] = len(fold.test)
    summary["evaluated_users"] = len(fold.ground_truth)
    summary["min_interactions"] = min_interactions
    summary["exclusion_stats"] = fold.exclusion_stats
    if fold.cutoff is not None:
        summary["cutoff"] = fold.cutoff.isoformat()
    return fold, summary


def _insufficient_data_notes(fold: EvaluationFold) -> str:
    notes: list[str] = []
    if len(fold.ground_truth) < _minimum_users():
        notes.append(
            f"Insufficient evaluable users: {len(fold.ground_truth)} available, "
            f"{_minimum_users()} required."
        )
    test_count = sum(len(items) for items in fold.ground_truth.values())
    if test_count < _minimum_test_interactions():
        notes.append(
            f"Insufficient held-out interactions: {test_count} available, "
            f"{_minimum_test_interactions()} required."
        )
    excluded = fold.exclusion_stats.get("users_excluded_insufficient_history", 0)
    if excluded:
        notes.append(
            f"Excluded {excluded} users below min_interactions="
            f"{fold.exclusion_stats.get('min_interactions')} "
            "(see exclusion_stats.reason)."
        )
    return " ".join(notes)


def _empty_metrics(*, k_values: list[int], fold: EvaluationFold) -> MetricSnapshot:
    zero = {k: 0.0 for k in k_values}
    return MetricSnapshot(
        precision_at_k=zero,
        recall_at_k=zero,
        map_at_k=zero,
        ndcg_at_k=zero,
        hit_rate_at_k=zero,
        evaluated_users=len(fold.ground_truth),
        test_interactions=sum(len(items) for items in fold.ground_truth.values()),
    )


def _configuration_payload(
    *,
    split: str,
    k_values: list[int],
    recommendation_limit: int,
    min_interactions: int,
    seed: int,
    cutoff: datetime | None,
    dataset_info: dict | None = None,
) -> dict:
    payload = {
        "split": split,
        "k_values": k_values,
        "recommendation_limit": recommendation_limit,
        "min_interactions": min_interactions,
        "seed": seed,
        "methodology": "temporal",
        "leakage_prevention": {
            "train_excludes_future_interactions": True,
            "features_built_from_train_only": True,
            "catalog_priors_disabled_by_default": not bool(
                getattr(settings, "EVAL_USE_CATALOG_PRIOR", False)
            ),
        },
    }
    if cutoff is not None:
        payload["cutoff"] = cutoff.isoformat()
    if dataset_info is not None:
        payload["dataset_info"] = dataset_info
    return payload


def evaluate_recommender(
    *,
    model_name: str,
    split: str = "temporal_leave_one_out",
    cutoff: datetime | None = None,
    k_values: list[int] | None = None,
    recommendation_limit: int | None = None,
    min_interactions: int | None = None,
    seed: int | None = None,
    recommender: BaseEvaluationRecommender | None = None,
) -> ModelEvaluationResult:
    k_values = k_values or _default_k_values()
    recommendation_limit = recommendation_limit or max(k_values)
    min_interactions = (
        min_interactions if min_interactions is not None else _minimum_user_interactions()
    )
    seed = _default_seed() if seed is None else int(seed)
    random.seed(seed)

    fold, dataset_info = _build_fold(split=split, cutoff=cutoff, min_interactions=min_interactions)
    notes = _insufficient_data_notes(fold)
    # Exclusion notes alone do not mark data insufficient.
    sufficient = (
        len(fold.ground_truth) >= _minimum_users()
        and sum(len(items) for items in fold.ground_truth.values()) >= _minimum_test_interactions()
    )
    if not sufficient and not notes:
        notes = _insufficient_data_notes(fold)

    configuration = _configuration_payload(
        split=split,
        k_values=k_values,
        recommendation_limit=recommendation_limit,
        min_interactions=min_interactions,
        seed=seed,
        cutoff=cutoff,
        dataset_info=dataset_info,
    )

    recommender = recommender or get_recommender(model_name, seed=seed)
    if not sufficient:
        return ModelEvaluationResult(
            model_name=recommender.name,
            model_version=recommender.version,
            metrics=_empty_metrics(k_values=k_values, fold=fold),
            sufficient_data=False,
            notes=notes,
            configuration=configuration,
        )

    user_ids = list(fold.ground_truth.keys())
    recommendations = recommender.recommend_for_users(
        fold=fold,
        user_ids=user_ids,
        limit=recommendation_limit,
    )
    metrics = compute_metric_snapshot(
        recommendations=recommendations,
        ground_truth=fold.ground_truth,
        relevance_grades=fold.relevance_grades,
        k_values=k_values,
    )
    return ModelEvaluationResult(
        model_name=recommender.name,
        model_version=recommender.version,
        metrics=metrics,
        sufficient_data=True,
        notes=notes,
        configuration=configuration,
    )


def compare_recommenders(
    *,
    model_names: list[str] | None = None,
    split: str = "temporal_leave_one_out",
    cutoff: datetime | None = None,
    k_values: list[int] | None = None,
    recommendation_limit: int | None = None,
    min_interactions: int | None = None,
    seed: int | None = None,
) -> ComparisonReport:
    k_values = k_values or _default_k_values()
    recommendation_limit = recommendation_limit or max(k_values)
    min_interactions = (
        min_interactions if min_interactions is not None else _minimum_user_interactions()
    )
    seed = _default_seed() if seed is None else int(seed)
    random.seed(seed)

    fold, dataset_info = _build_fold(split=split, cutoff=cutoff, min_interactions=min_interactions)
    notes = _insufficient_data_notes(fold)
    sufficient = (
        len(fold.ground_truth) >= _minimum_users()
        and sum(len(items) for items in fold.ground_truth.values()) >= _minimum_test_interactions()
    )

    model_names = model_names or [
        "popularity",
        "content_based",
        "collaborative_filtering",
        "hybrid",
    ]
    configuration = _configuration_payload(
        split=split,
        k_values=k_values,
        recommendation_limit=recommendation_limit,
        min_interactions=min_interactions,
        seed=seed,
        cutoff=cutoff,
    )
    configuration["models"] = model_names

    results: list[ModelEvaluationResult] = []
    for model_name in model_names:
        recommender = get_recommender(model_name, seed=seed)
        if not sufficient:
            results.append(
                ModelEvaluationResult(
                    model_name=recommender.name,
                    model_version=recommender.version,
                    metrics=_empty_metrics(k_values=k_values, fold=fold),
                    sufficient_data=False,
                    notes=notes,
                    configuration=configuration,
                )
            )
            continue

        recommendations = recommender.recommend_for_users(
            fold=fold,
            user_ids=list(fold.ground_truth.keys()),
            limit=recommendation_limit,
        )
        metrics = compute_metric_snapshot(
            recommendations=recommendations,
            ground_truth=fold.ground_truth,
            relevance_grades=fold.relevance_grades,
            k_values=k_values,
        )
        results.append(
            ModelEvaluationResult(
                model_name=recommender.name,
                model_version=recommender.version,
                metrics=metrics,
                sufficient_data=True,
                notes="",
                configuration=configuration,
            )
        )

    return ComparisonReport(
        generated_at=timezone.now(),
        dataset_info=dataset_info,
        configuration=configuration,
        results=results,
        sufficient_data=sufficient,
        notes=notes,
    )
