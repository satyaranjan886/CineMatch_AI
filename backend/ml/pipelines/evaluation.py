"""Evaluation pipeline entrypoints."""

from __future__ import annotations

from datetime import datetime

from django.utils import timezone

from ml.evaluation.evaluator import compare_recommenders, evaluate_recommender
from ml.evaluation.types import ComparisonReport, ModelEvaluationResult


def run_recommender_evaluation(
    *,
    model_name: str,
    split: str = "temporal_leave_one_out",
    cutoff: datetime | None = None,
    k_values: list[int] | None = None,
    recommendation_limit: int | None = None,
    min_interactions: int | None = None,
    seed: int | None = None,
    persist: bool = True,
) -> ModelEvaluationResult:
    result = evaluate_recommender(
        model_name=model_name,
        split=split,
        cutoff=cutoff,
        k_values=k_values,
        recommendation_limit=recommendation_limit,
        min_interactions=min_interactions,
        seed=seed,
    )
    if persist:
        persist_evaluation_result(result, report_type="single")
    return result


def run_recommender_comparison(
    *,
    model_names: list[str] | None = None,
    split: str = "temporal_leave_one_out",
    cutoff: datetime | None = None,
    k_values: list[int] | None = None,
    recommendation_limit: int | None = None,
    min_interactions: int | None = None,
    seed: int | None = None,
    persist: bool = True,
) -> ComparisonReport:
    report = compare_recommenders(
        model_names=model_names,
        split=split,
        cutoff=cutoff,
        k_values=k_values,
        recommendation_limit=recommendation_limit,
        min_interactions=min_interactions,
        seed=seed,
    )
    if persist:
        persist_comparison_report(report)
    return report


def persist_evaluation_result(
    result: ModelEvaluationResult, *, report_type: str = "single"
) -> None:
    from apps.recommendations.models import RecommendationEvaluationReport

    RecommendationEvaluationReport.objects.create(
        model_name=result.model_name,
        model_version=result.model_version,
        report_type=report_type,
        dataset_info=result.configuration.get("dataset_info", {}),
        configuration=result.configuration,
        metrics=result.metrics.as_dict(),
        sufficient_data=result.sufficient_data,
        notes=result.notes,
        evaluated_at=timezone.now(),
    )


def persist_comparison_report(report: ComparisonReport) -> None:
    from apps.recommendations.models import RecommendationEvaluationReport

    RecommendationEvaluationReport.objects.create(
        model_name="comparison",
        model_version="multi-model",
        report_type="comparison",
        dataset_info=report.dataset_info,
        configuration=report.configuration,
        metrics=report.as_dict(),
        sufficient_data=report.sufficient_data,
        notes=report.notes,
        evaluated_at=report.generated_at,
    )
