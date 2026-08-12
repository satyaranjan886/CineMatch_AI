"""User accounts, authentication identity, and profiles."""

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from apps.accounts.managers import UserManager
from apps.common.models import TimeStampedModel, UUIDModel


class User(AbstractBaseUser, PermissionsMixin, UUIDModel):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        db_table = "users"
        verbose_name = "user"
        verbose_name_plural = "users"
        ordering = ["-date_joined"]
        indexes = [
            models.Index(fields=["is_active", "date_joined"], name="users_active_joined_idx"),
        ]

    def __str__(self) -> str:
        return self.email

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def get_primary_profile(self) -> "Profile | None":
        return self.profiles.filter(is_primary=True).first()

    @property
    def profile(self) -> "Profile | None":
        """Shortcut to the user's primary profile."""
        return self.get_primary_profile()


class Profile(UUIDModel, TimeStampedModel):
    """
    Viewer profile. Uses ForeignKey (not OneToOne) so multiple profiles per
    account can be added later (e.g. kids profile). Exactly one primary profile
    per user is enforced by a partial unique constraint.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profiles",
    )
    is_primary = models.BooleanField(default=True, db_index=True)
    display_name = models.CharField(max_length=150, blank=True)
    avatar_url = models.URLField(max_length=500, blank=True)
    preferred_language = models.CharField(max_length=10, default="en")
    bio = models.CharField(max_length=500, blank=True)
    country = models.CharField(max_length=2, blank=True)
    timezone = models.CharField(max_length=64, default="UTC")
    onboarding_completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "profiles"
        verbose_name = "profile"
        verbose_name_plural = "profiles"
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(is_primary=True),
                name="profiles_one_primary_per_user",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "is_primary"], name="profiles_user_primary_idx"),
        ]

    def __str__(self) -> str:
        return self.display_name or str(self.user)

    @property
    def onboarding_completed(self) -> bool:
        return self.onboarding_completed_at is not None


class UserPreference(UUIDModel, TimeStampedModel):
    """Explicit taste signals used by the recommendation engine in later phases."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="preferences",
    )
    preferred_languages = models.JSONField(default=list, blank=True)
    preferred_decades = models.JSONField(default=list, blank=True)
    favorite_genres = models.ManyToManyField(
        "movies.Genre",
        blank=True,
        related_name="preferred_by_users",
    )
    favorite_actors = models.ManyToManyField(
        "movies.Actor",
        blank=True,
        related_name="preferred_by_users",
    )
    favorite_directors = models.ManyToManyField(
        "movies.Director",
        blank=True,
        related_name="preferred_by_users",
    )

    class Meta:
        db_table = "user_preferences"
        verbose_name = "user preference"
        verbose_name_plural = "user preferences"

    def __str__(self) -> str:
        return f"Preferences for {self.user.email}"
