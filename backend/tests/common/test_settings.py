from django.conf import settings


def test_recommendation_weights_are_configured_and_sum_to_one():
    weights = settings.RECOMMENDATION_WEIGHTS
    expected_keys = {
        "collaborative",
        "content",
        "genre_preference",
        "popularity",
        "trending",
        "freshness",
        "affinity",
    }
    assert set(weights) == expected_keys
    assert round(sum(weights.values()), 2) == 1.0
