"""Offline evaluation helpers for collaborative filtering.

Training-time CF metrics now use the temporal evaluation framework
(`ml.evaluation`). Functions in this module remain for unit tests and
legacy non-temporal leave-one-out checks. Prefer
`ml.evaluation.split.temporal_leave_one_out` for any new work.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import numpy as np
from scipy.sparse import csr_matrix

from ml.collaborative.model import CollaborativeFilteringModel


@dataclass(frozen=True)
class EvaluationMetrics:
    hit_rate_at_k: float
    precision_at_k: float
    recall_at_k: float
    evaluated_users: int
    held_out_interactions: int

    def as_dict(self) -> dict[str, float | int]:
        return {
            "hit_rate_at_k": round(self.hit_rate_at_k, 6),
            "precision_at_k": round(self.precision_at_k, 6),
            "recall_at_k": round(self.recall_at_k, 6),
            "evaluated_users": self.evaluated_users,
            "held_out_interactions": self.held_out_interactions,
        }


def leave_one_out_records(
    records: list[tuple[int, int, float]],
) -> tuple[list[tuple[int, int, float]], list[tuple[int, int]]]:
    by_user: dict[int, list[tuple[int, float]]] = defaultdict(list)
    for user_index, item_index, weight in records:
        by_user[user_index].append((item_index, weight))

    train_records: list[tuple[int, int, float]] = []
    test_pairs: list[tuple[int, int]] = []

    for user_index, items in by_user.items():
        if len(items) < 2:
            train_records.extend((user_index, item_index, weight) for item_index, weight in items)
            continue
        for item_index, weight in items[:-1]:
            train_records.append((user_index, item_index, weight))
        held_out_item, _ = items[-1]
        test_pairs.append((user_index, held_out_item))

    return train_records, test_pairs


def build_matrix_from_records(
    records: list[tuple[int, int, float]],
    *,
    user_count: int,
    item_count: int,
) -> csr_matrix:
    if not records:
        return csr_matrix((user_count, item_count), dtype=np.float32)

    rows = [record[0] for record in records]
    cols = [record[1] for record in records]
    data = [record[2] for record in records]
    return csr_matrix((data, (rows, cols)), shape=(user_count, item_count), dtype=np.float32)


def evaluate_leave_one_out(
    model: CollaborativeFilteringModel,
    *,
    train_matrix: csr_matrix,
    test_pairs: list[tuple[int, int]],
    k: int = 10,
) -> EvaluationMetrics:
    if not test_pairs:
        return EvaluationMetrics(
            hit_rate_at_k=0.0,
            precision_at_k=0.0,
            recall_at_k=0.0,
            evaluated_users=0,
            held_out_interactions=0,
        )

    hits = 0
    precision_total = 0.0
    recall_total = 0.0

    for user_index, held_out_item in test_pairs:
        recommendations = model.recommend(
            user_index,
            train_matrix[user_index],
            limit=k,
        )
        recommended_items = {candidate.item_index for candidate in recommendations}
        hit = held_out_item in recommended_items
        hits += int(hit)
        precision_total += int(hit) / k
        recall_total += int(hit)

    evaluated_users = len(test_pairs)
    return EvaluationMetrics(
        hit_rate_at_k=hits / evaluated_users,
        precision_at_k=precision_total / evaluated_users,
        recall_at_k=recall_total / evaluated_users,
        evaluated_users=evaluated_users,
        held_out_interactions=evaluated_users,
    )
