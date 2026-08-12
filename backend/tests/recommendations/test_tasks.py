"""Celery tasks for recommendation score refresh."""

import pytest

from apps.recommendations.tasks import update_popularity_scores, update_trending_scores
from tests.movies.factories import MovieFactory


@pytest.mark.django_db
def test_update_popularity_scores_task():
    MovieFactory(title="Task Popular")

    result = update_popularity_scores()

    assert result["strategy"] == "popular"
    assert result["count"] >= 1


@pytest.mark.django_db
def test_update_trending_scores_task():
    result = update_trending_scores()

    assert result["strategy"] == "trending"
    assert "24" in result["windows"]
    assert "168" in result["windows"]
