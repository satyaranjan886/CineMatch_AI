from apps.accounts.models import Profile

from .factories import UserFactory


def test_user_factory_creates_profile(db):
    user = UserFactory(first_name="Nia")
    assert user.check_password("test-pass-123")
    assert Profile.objects.filter(user=user, display_name="Nia").exists()
