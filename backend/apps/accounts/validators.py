from django.contrib.auth.password_validation import validate_password


def validate_strong_password(password: str, *, user=None) -> None:
    """Run Django password validators for API registration and password changes."""
    validate_password(password, user=user)
