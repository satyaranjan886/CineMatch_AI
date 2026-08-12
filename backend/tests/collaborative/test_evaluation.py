"""Collaborative filtering evaluation tests."""

from ml.collaborative.evaluation import (
    build_matrix_from_records,
    evaluate_leave_one_out,
    leave_one_out_records,
)
from ml.collaborative.model import ALSCollaborativeFilteringModel


def test_leave_one_out_split_holds_back_one_item_per_user():
    records = [
        (0, 0, 1.0),
        (0, 1, 2.0),
        (0, 2, 3.0),
        (1, 3, 1.5),
    ]
    train_records, test_pairs = leave_one_out_records(records)

    assert (0, 2) in test_pairs
    assert (0, 2, 3.0) not in train_records
    assert (1, 3, 1.5) in train_records
    assert (1,) not in {pair[0] for pair in test_pairs}


def test_evaluate_leave_one_out_computes_real_metrics():
    records = [
        (0, 0, 5.0),
        (0, 1, 4.0),
        (0, 2, 3.0),
        (1, 0, 4.0),
        (1, 1, 5.0),
        (1, 2, 3.0),
        (2, 0, 3.0),
        (2, 1, 4.0),
        (2, 2, 5.0),
    ]
    train_records, test_pairs = leave_one_out_records(records)
    train_matrix = build_matrix_from_records(train_records, user_count=3, item_count=3)

    model = ALSCollaborativeFilteringModel(
        factors=4, iterations=10, regularization=0.1, random_state=7
    )
    model.fit(train_matrix)
    metrics = evaluate_leave_one_out(model, train_matrix=train_matrix, test_pairs=test_pairs, k=2)

    assert metrics.evaluated_users == 3
    assert 0.0 <= metrics.hit_rate_at_k <= 1.0
    assert 0.0 <= metrics.precision_at_k <= 1.0
    assert 0.0 <= metrics.recall_at_k <= 1.0
    assert metrics.recall_at_k == metrics.hit_rate_at_k
