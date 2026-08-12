import uuid

import pytest
from django.db import IntegrityError

from apps.accounts.models import Profile, User


@pytest.mark.django_db
def test_create_user_uses_uuid_primary_key_and_email_login():
    user = User.objects.create_user(email="sam@example.com", password="secret-pass-123")

    assert isinstance(user.id, uuid.UUID)
    assert user.email == "sam@example.com"
    assert user.check_password("secret-pass-123")
    assert user.is_active is True
    assert user.is_staff is False
    assert user.USERNAME_FIELD == "email"


@pytest.mark.django_db
def test_create_user_requires_email():
    with pytest.raises(ValueError, match="Email is required"):
        User.objects.create_user(email="", password="secret-pass-123")


@pytest.mark.django_db
def test_email_is_unique():
    User.objects.create_user(email="dup@example.com", password="secret-pass-123")
    with pytest.raises(IntegrityError):
        User.objects.create_user(email="dup@example.com", password="other-pass-123")


@pytest.mark.django_db
def test_profile_is_created_for_new_user():
    user = User.objects.create_user(
        email="ada@example.com",
        password="secret-pass-123",
        first_name="Ada",
    )

    profile = Profile.objects.get(user=user, is_primary=True)
    assert profile.display_name == "Ada"
    assert profile.preferred_language == "en"
    assert user.profile.id == profile.id


@pytest.mark.django_db
def test_user_preference_created_for_new_user():
    user = User.objects.create_user(email="pref@example.com", password="secret-pass-123")
    from apps.accounts.models import UserPreference

    assert UserPreference.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_multiple_profiles_allowed_with_one_primary():
    user = User.objects.create_user(email="multi@example.com", password="secret-pass-123")
    Profile.objects.create(user=user, display_name="Kids", is_primary=False)
    assert user.profiles.count() == 2
    assert user.get_primary_profile().display_name == "multi"


@pytest.mark.django_db
def test_create_superuser_flags():
    admin = User.objects.create_superuser(email="admin@example.com", password="secret-pass-123")
    assert admin.is_staff is True
    assert admin.is_superuser is True
