from django.db import transaction

from apps.accounts.models import User
from apps.accounts.validators import validate_strong_password


class RegistrationError(Exception):
    def __init__(self, message: str, *, code: str = "invalid"):
        self.message = message
        self.code = code
        super().__init__(message)


@transaction.atomic
def register_user(
    *,
    email: str,
    password: str,
    first_name: str = "",
    last_name: str = "",
    display_name: str = "",
) -> User:
    normalized_email = email.strip().lower()
    if User.objects.filter(email__iexact=normalized_email).exists():
        raise RegistrationError("A user with this email already exists.", code="duplicate_email")

    user = User(email=normalized_email, first_name=first_name, last_name=last_name)
    validate_strong_password(password, user=user)
    user.set_password(password)
    user.save()

    profile = user.get_primary_profile()
    if profile and display_name:
        profile.display_name = display_name
        profile.save(update_fields=["display_name", "updated_at"])

    return user
