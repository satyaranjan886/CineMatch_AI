"""End-to-end evaluation framework tests."""

from datetime import timedelta
from io import StringIO

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.utils import timezone

from apps.accounts.models import User
from apps.interactions.models import Like
from apps.recommendations.models import RecommendationEvaluationReport
from ml.content_based.index import ContentSimilarityIndex
from ml.evaluation.evaluator import compare_recommenders, evaluate_recommender
from ml.pipelines.evaluation import run_recommender_comparison, run_recommender_evaluation
from tests.movies.factories import MovieFactory


@pytest.fixture(autouse=True)
def clear_eval_state():
    cache.clear()
    ContentSimilarityIndex.invalidate()
    yield
    cache.clear()
    ContentSimilarityIndex.invalidate()


@pytest.fixture
def eval_users(db):
    return [
        User.objects.create_user(email=f"eval-{index}@example.com", password="test-pass-123")
        for index in range(6)
    ]


@pytest.fixture
def eval_catalog(db, eval_users, settings):
    settings.EVAL_MIN_USERS = 3
    settings.EVAL_MIN_TEST_INTERACTIONS = 3
    settings.CF_ALS_FACTORS = 8
    settings.CF_ALS_ITERATIONS = 8

    movies = [
        MovieFactory(
            title=f"Eval Movie {index}",
            overview=f"science fiction adventure mission number {index}",
            popularity=50 - index,
            vote_average=8.0 - index * 0.1,
        )
        for index in range(10)
    ]

    now = timezone.now()
    for user_index, user in enumerate(eval_users):
        # Give each user several temporally ordered likes.
        for offset, movie in enumerate(movies[user_index : user_index + 4]):
            like = Like.objects.create(user=user, movie=movie)
            Like.objects.filter(pk=like.pk).update(created_at=now - timedelta(days=10 - offset))

    return {"users": eval_users, "movies": movies}


@pytest.mark.django_db
def test_evaluate_recommender_reports_real_metrics(eval_catalog):
    result = evaluate_recommender(model_name="popularity", k_values=[5, 10])
    assert result.sufficient_data is True
    assert result.metrics.evaluated_users >= 3
    assert 0.0 <= result.metrics.precision_at_k[5] <= 1.0
    assert 0.0 <= result.metrics.recall_at_k[5] <= 1.0
    assert 0.0 <= result.metrics.map_at_k[5] <= 1.0
    assert 0.0 <= result.metrics.ndcg_at_k[5] <= 1.0
    assert 0.0 <= result.metrics.hit_rate_at_k[5] <= 1.0


@pytest.mark.django_db
def test_compare_recommenders_covers_all_models(eval_catalog):
    report = compare_recommenders(k_values=[5, 10, 20])
    assert report.sufficient_data is True
    names = {result.model_name for result in report.results}
    assert names == {
        "popularity",
        "content_based",
        "collaborative_filtering",
        "hybrid",
    }
    for result in report.results:
        assert result.sufficient_data is True
        assert set(result.metrics.precision_at_k) == {5, 10, 20}


@pytest.mark.django_db
def test_insufficient_data_is_reported_clearly(db, settings):
    settings.EVAL_MIN_USERS = 5
    settings.EVAL_MIN_TEST_INTERACTIONS = 10
    user = User.objects.create_user(email="lonely@example.com", password="test-pass-123")
    movie = MovieFactory(title="Only Movie")
    Like.objects.create(user=user, movie=movie)

    result = evaluate_recommender(model_name="popularity")
    assert result.sufficient_data is False
    assert "Insufficient" in result.notes


@pytest.mark.django_db
def test_persist_evaluation_metadata(eval_catalog):
    result = run_recommender_evaluation(model_name="content_based", k_values=[5], persist=True)
    report = RecommendationEvaluationReport.objects.get(model_name=result.model_name)
    assert report.model_version == result.model_version
    assert report.metrics["evaluated_users"] == result.metrics.evaluated_users
    assert report.configuration["k_values"] == [5]
    assert report.evaluated_at is not None


@pytest.mark.django_db
def test_persist_comparison_report(eval_catalog):
    report = run_recommender_comparison(k_values=[5], persist=True)
    stored = RecommendationEvaluationReport.objects.get(report_type="comparison")
    assert stored.model_name == "comparison"
    assert stored.metrics["sufficient_data"] is True
    assert len(stored.metrics["results"]) == 4
    assert report.sufficient_data is True


@pytest.mark.django_db
def test_evaluate_recommender_command_json(eval_catalog):
    out = StringIO()
    call_command(
        "evaluate_recommender",
        "--model",
        "popularity",
        "--k",
        "5",
        "10",
        "--format",
        "json",
        "--no-persist",
        stdout=out,
    )
    payload = out.getvalue()
    assert '"model_name": "popularity"' in payload
    assert "precision_at_k" in payload


@pytest.mark.django_db
def test_evaluate_recommender_command_supports_seed_and_min_interactions(eval_catalog):
    out = StringIO()
    call_command(
        "evaluate_recommender",
        "--model",
        "popularity",
        "--k",
        "5",
        "10",
        "--min-interactions",
        "2",
        "--seed",
        "123",
        "--format",
        "json",
        "--no-persist",
        stdout=out,
    )
    payload = out.getvalue()
    assert '"seed": 123' in payload
    assert '"min_interactions": 2' in payload
    assert "precision_at_k" in payload


@pytest.mark.django_db
def test_compare_recommenders_command_table(eval_catalog):
    out = StringIO()
    call_command(
        "compare_recommenders",
        "--models",
        "popularity",
        "content_based",
        "--k",
        "5",
        "--format",
        "table",
        "--no-persist",
        stdout=out,
    )
    text = out.getvalue()
    assert "Recommendation Model Comparison" in text
    assert "popularity" in text
    assert "content_based" in text
