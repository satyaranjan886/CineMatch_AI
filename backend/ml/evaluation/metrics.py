"""Offline ranking metrics for recommendation evaluation."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from uuid import UUID

from ml.evaluation.types import MetricSnapshot


def _precision_at_k(recommended: Sequence[UUID], relevant: set[UUID], k: int) -> float:
    if k <= 0:
        return 0.0
    top_k = recommended[:k]
    if not top_k:
        return 0.0
    return len(set(top_k) & relevant) / k


def _recall_at_k(recommended: Sequence[UUID], relevant: set[UUID], k: int) -> float:
    if not relevant:
        return 0.0
    top_k = recommended[:k]
    return len(set(top_k) & relevant) / len(relevant)


def _average_precision_at_k(recommended: Sequence[UUID], relevant: set[UUID], k: int) -> float:
    if not relevant:
        return 0.0
    hits = 0
    precision_sum = 0.0
    for index, item in enumerate(recommended[:k], start=1):
        if item in relevant:
            hits += 1
            precision_sum += hits / index
    if hits == 0:
        return 0.0
    return precision_sum / min(len(relevant), k)


def _dcg_at_k(recommended: Sequence[UUID], relevance: Mapping[UUID, float], k: int) -> float:
    score = 0.0
    for index, item in enumerate(recommended[:k], start=1):
        rel = relevance.get(item, 0.0)
        if rel <= 0:
            continue
        score += rel / math.log2(index + 1)
    return score


def _ndcg_at_k(recommended: Sequence[UUID], relevance: Mapping[UUID, float], k: int) -> float:
    dcg = _dcg_at_k(recommended, relevance, k)
    ideal_items = sorted(relevance.items(), key=lambda item: item[1], reverse=True)
    ideal = _dcg_at_k([item_id for item_id, _ in ideal_items], relevance, k)
    if ideal <= 0:
        return 0.0
    return dcg / ideal


def compute_metric_snapshot(
    *,
    recommendations: dict[UUID, list[UUID]],
    ground_truth: dict[UUID, set[UUID]],
    relevance_grades: dict[UUID, dict[UUID, float]],
    k_values: list[int],
) -> MetricSnapshot:
    evaluated_users = len(ground_truth)
    test_interactions = sum(len(items) for items in ground_truth.values())

    precision_totals = {k: 0.0 for k in k_values}
    recall_totals = {k: 0.0 for k in k_values}
    map_totals = {k: 0.0 for k in k_values}
    ndcg_totals = {k: 0.0 for k in k_values}
    hit_totals = {k: 0 for k in k_values}

    if evaluated_users == 0:
        zero = {k: 0.0 for k in k_values}
        return MetricSnapshot(
            precision_at_k=zero,
            recall_at_k=zero,
            map_at_k=zero,
            ndcg_at_k=zero,
            hit_rate_at_k=zero,
            evaluated_users=0,
            test_interactions=0,
        )

    for user_id, relevant in ground_truth.items():
        recommended = recommendations.get(user_id, [])
        grades = relevance_grades.get(user_id, {})
        for k in k_values:
            if _recall_at_k(recommended, relevant, k) > 0:
                hit_totals[k] += 1
            precision_totals[k] += _precision_at_k(recommended, relevant, k)
            recall_totals[k] += _recall_at_k(recommended, relevant, k)
            map_totals[k] += _average_precision_at_k(recommended, relevant, k)
            ndcg_totals[k] += _ndcg_at_k(recommended, grades, k)

    return MetricSnapshot(
        precision_at_k={k: precision_totals[k] / evaluated_users for k in k_values},
        recall_at_k={k: recall_totals[k] / evaluated_users for k in k_values},
        map_at_k={k: map_totals[k] / evaluated_users for k in k_values},
        ndcg_at_k={k: ndcg_totals[k] / evaluated_users for k in k_values},
        hit_rate_at_k={k: hit_totals[k] / evaluated_users for k in k_values},
        evaluated_users=evaluated_users,
        test_interactions=test_interactions,
    )
