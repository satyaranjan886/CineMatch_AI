import pytest

from ml.collaborative.recommender import ActiveCollaborativeRecommender


@pytest.fixture
def other_user(db):
    from apps.accounts.models import User

    return User.objects.create_user(email="other@example.com", password="test-pass-123")


@pytest.fixture(autouse=True)
def reset_cf_cache():
    ActiveCollaborativeRecommender.invalidate()
    yield
    ActiveCollaborativeRecommender.invalidate()
