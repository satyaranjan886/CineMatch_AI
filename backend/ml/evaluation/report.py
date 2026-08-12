"""Human-readable and JSON report formatting."""

from __future__ import annotations

import json

from ml.evaluation.types import ComparisonReport, ModelEvaluationResult


def format_model_result_table(result: ModelEvaluationResult) -> str:
    lines = [
        f"Model: {result.model_name} ({result.model_version})",
        f"Sufficient data: {result.sufficient_data}",
    ]
    if result.notes:
        lines.append(f"Notes: {result.notes}")
    lines.append("")
    header = f"{'Metric':<16}" + "".join(f"@{k:<8}" for k in sorted(result.metrics.precision_at_k))
    lines.append(header)
    lines.append("-" * len(header))
    for label, values in [
        ("Precision", result.metrics.precision_at_k),
        ("Recall", result.metrics.recall_at_k),
        ("MAP", result.metrics.map_at_k),
        ("NDCG", result.metrics.ndcg_at_k),
        ("Hit Rate", result.metrics.hit_rate_at_k),
    ]:
        row = f"{label:<16}" + "".join(f"{values[k]:<8.4f}" for k in sorted(values))
        lines.append(row)
    lines.append("")
    lines.append(
        f"Evaluated users: {result.metrics.evaluated_users} | "
        f"Held-out interactions: {result.metrics.test_interactions}"
    )
    return "\n".join(lines)


def format_comparison_table(report: ComparisonReport) -> str:
    lines = [
        "Recommendation Model Comparison",
        f"Generated at: {report.generated_at.isoformat()}",
        f"Sufficient data: {report.sufficient_data}",
    ]
    if report.notes:
        lines.append(f"Notes: {report.notes}")
    lines.append("")
    lines.append("Dataset")
    for key, value in report.dataset_info.items():
        lines.append(f"  {key}: {value}")
    lines.append("")

    k_values = report.configuration.get("k_values", [])
    for k in k_values:
        lines.append(f"Metrics @ {k}")
        header = (
            f"{'Model':<24}{'Precision':<12}{'Recall':<12}{'MAP':<12}{'NDCG':<12}{'Hit Rate':<12}"
        )
        lines.append(header)
        lines.append("-" * len(header))
        for result in report.results:
            lines.append(
                f"{result.model_name:<24}"
                f"{result.metrics.precision_at_k.get(k, 0.0):<12.4f}"
                f"{result.metrics.recall_at_k.get(k, 0.0):<12.4f}"
                f"{result.metrics.map_at_k.get(k, 0.0):<12.4f}"
                f"{result.metrics.ndcg_at_k.get(k, 0.0):<12.4f}"
                f"{result.metrics.hit_rate_at_k.get(k, 0.0):<12.4f}"
            )
        lines.append("")
    return "\n".join(lines)


def result_to_json(result: ModelEvaluationResult) -> str:
    payload = {
        "model_name": result.model_name,
        "model_version": result.model_version,
        "sufficient_data": result.sufficient_data,
        "notes": result.notes,
        "configuration": result.configuration,
        "metrics": result.metrics.as_dict(),
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def comparison_to_json(report: ComparisonReport) -> str:
    return json.dumps(report.as_dict(), indent=2, sort_keys=True)
