"""Time-aware train/test splits for recommendation evaluation."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from ml.evaluation.types import EvaluationFold, TimedInteraction

# Default: need ≥2 interactions for leave-one-out (history + future holdout).
DEFAULT_MIN_INTERACTIONS = 2


def temporal_leave_one_out(
    interactions: list[TimedInteraction],
    *,
    min_interactions: int = DEFAULT_MIN_INTERACTIONS,
) -> EvaluationFold:
    """
    Hold out each user's most recent interaction for testing.

    Interactions are sorted by timestamp ascending before splitting so future
    events are never used to predict earlier held-out items.

    Users with fewer than ``min_interactions`` total interactions are excluded
    from personalized evaluation (no test row). Their interactions remain in the
    train fold so item coverage is preserved for other users. Exclusions are
    recorded on the fold — they are not silent.
    """
    if min_interactions < 2:
        raise ValueError("min_interactions must be >= 2 for temporal leave-one-out")

    by_user: dict = defaultdict(list)
    for interaction in interactions:
        by_user[interaction.user_id].append(interaction)

    train: list[TimedInteraction] = []
    test: list[TimedInteraction] = []
    excluded_insufficient = 0

    for user_interactions in by_user.values():
        ordered = sorted(user_interactions, key=lambda item: (item.timestamp, str(item.movie_id)))
        if len(ordered) < min_interactions:
            # Keep history in train for matrix/popularity coverage; no hold-out.
            train.extend(ordered)
            excluded_insufficient += 1
            continue
        train.extend(ordered[:-1])
        test.append(ordered[-1])

    reason = (
        f"Users with fewer than {min_interactions} interactions are excluded from "
        "personalized temporal evaluation because a reliable history→future split "
        "requires enough prior events. Their interactions remain in the train fold "
        "so other users' models can still observe those items; they are not deleted."
    )
    return EvaluationFold(
        train=train,
        test=test,
        split_strategy="temporal_leave_one_out",
        exclusion_stats={
            "min_interactions": min_interactions,
            "users_excluded_insufficient_history": excluded_insufficient,
            "users_evaluated": len({item.user_id for item in test}),
            "reason": reason,
        },
    )


def temporal_cutoff_split(
    interactions: list[TimedInteraction],
    cutoff: datetime,
    *,
    min_interactions: int = DEFAULT_MIN_INTERACTIONS,
) -> EvaluationFold:
    """
    Split interactions by an absolute timestamp cutoff.

    Train: timestamp < cutoff. Test: timestamp >= cutoff.
    Users with fewer than ``min_interactions`` train interactions are excluded
    from evaluation (their test rows are dropped) so cold users do not inflate
    metrics. Exclusion counts are recorded on the fold.
    """
    train = [interaction for interaction in interactions if interaction.timestamp < cutoff]
    test = [interaction for interaction in interactions if interaction.timestamp >= cutoff]

    train_counts: dict = defaultdict(int)
    for interaction in train:
        train_counts[interaction.user_id] += 1

    filtered_test: list[TimedInteraction] = []
    excluded_insufficient = 0
    excluded_users: set = set()
    for interaction in test:
        if train_counts[interaction.user_id] < min_interactions:
            if interaction.user_id not in excluded_users:
                excluded_insufficient += 1
                excluded_users.add(interaction.user_id)
            continue
        filtered_test.append(interaction)

    reason = (
        f"Users with fewer than {min_interactions} train interactions before the "
        "cutoff are excluded from personalized evaluation. Test interactions for "
        "those users are omitted from scoring; train data is retained."
    )
    return EvaluationFold(
        train=train,
        test=filtered_test,
        split_strategy="temporal_cutoff",
        cutoff=cutoff,
        exclusion_stats={
            "min_interactions": min_interactions,
            "users_excluded_insufficient_history": excluded_insufficient,
            "users_evaluated": len({item.user_id for item in filtered_test}),
            "cutoff": cutoff.isoformat(),
            "reason": reason,
        },
    )


def assert_no_future_in_train(fold: EvaluationFold) -> None:
    """Raise AssertionError if any user's train interactions are after their test times."""
    test_by_user = fold.test_by_user
    for user_id, train_items in fold.train_by_user.items():
        test_items = test_by_user.get(user_id)
        if not test_items:
            continue
        earliest_test = min(item.timestamp for item in test_items)
        for item in train_items:
            if item.timestamp > earliest_test:
                raise AssertionError(
                    f"Future leakage: user {user_id} has train interaction at "
                    f"{item.timestamp} after test cutoff {earliest_test}"
                )
            if fold.cutoff is not None and item.timestamp >= fold.cutoff:
                raise AssertionError(
                    f"Future leakage: train interaction at {item.timestamp} "
                    f"is not before cutoff {fold.cutoff}"
                )
