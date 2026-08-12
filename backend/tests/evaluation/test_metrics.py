"""Offline ranking metric unit tests."""

from uuid import uuid4

from ml.evaluation.metrics import compute_metric_snapshot


def test_metrics_perfect_ranking():
    item_a = uuid4()
    item_b = uuid4()
    item_c = uuid4()
    user = uuid4()

    metrics = compute_metric_snapshot(
        recommendations={user: [item_a, item_b, item_c]},
        ground_truth={user: {item_a, item_b}},
        relevance_grades={user: {item_a: 5.0, item_b: 4.0}},
        k_values=[2, 5],
    )

    assert metrics.evaluated_users == 1
    assert metrics.precision_at_k[2] == 1.0
    assert metrics.recall_at_k[2] == 1.0
    assert metrics.hit_rate_at_k[2] == 1.0
    assert metrics.map_at_k[2] == 1.0
    assert metrics.ndcg_at_k[2] == 1.0


def test_metrics_miss_all():
    relevant = uuid4()
    user = uuid4()
    metrics = compute_metric_snapshot(
        recommendations={user: [uuid4(), uuid4()]},
        ground_truth={user: {relevant}},
        relevance_grades={user: {relevant: 1.0}},
        k_values=[5],
    )
    assert metrics.precision_at_k[5] == 0.0
    assert metrics.recall_at_k[5] == 0.0
    assert metrics.hit_rate_at_k[5] == 0.0
    assert metrics.map_at_k[5] == 0.0
    assert metrics.ndcg_at_k[5] == 0.0


def test_metrics_average_across_users():
    user_a = uuid4()
    user_b = uuid4()
    hit = uuid4()
    miss = uuid4()

    metrics = compute_metric_snapshot(
        recommendations={
            user_a: [hit],
            user_b: [miss],
        },
        ground_truth={
            user_a: {hit},
            user_b: {hit},
        },
        relevance_grades={
            user_a: {hit: 1.0},
            user_b: {hit: 1.0},
        },
        k_values=[1],
    )

    assert metrics.hit_rate_at_k[1] == 0.5
    assert metrics.recall_at_k[1] == 0.5
    assert metrics.precision_at_k[1] == 0.5
