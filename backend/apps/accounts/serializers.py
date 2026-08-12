from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Profile, UserPreference
from apps.accounts.services.registration import RegistrationError, register_user
from apps.movies.models import Actor, Director, Genre

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8, trim_whitespace=False)
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    display_name = serializers.CharField(required=False, allow_blank=True, max_length=150)

    def validate_password(self, value: str) -> str:
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value

    def create(self, validated_data):
        try:
            return register_user(**validated_data)
        except RegistrationError as exc:
            if exc.code == "duplicate_email":
                raise serializers.ValidationError({"email": [exc.message]}) from exc
            raise serializers.ValidationError({"detail": exc.message}) from exc


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = User.USERNAME_FIELD

    def validate(self, attrs):
        try:
            return super().validate(attrs)
        except AuthenticationFailed as exc:
            raise AuthenticationFailed("Invalid credentials.") from exc


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        refresh = attrs.get("refresh")
        if not refresh:
            raise serializers.ValidationError({"refresh": ["Refresh token is required."]})
        return attrs

    def save(self, **kwargs):
        token = RefreshToken(self.validated_data["refresh"])
        token.blacklist()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "first_name", "last_name", "date_joined", "is_staff")
        read_only_fields = fields


class ProfileSerializer(serializers.ModelSerializer):
    onboarding_completed = serializers.BooleanField(read_only=True)

    class Meta:
        model = Profile
        fields = (
            "id",
            "is_primary",
            "display_name",
            "avatar_url",
            "preferred_language",
            "bio",
            "country",
            "timezone",
            "onboarding_completed",
            "onboarding_completed_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "is_primary", "onboarding_completed", "created_at", "updated_at")


class ProfileUpdateSerializer(serializers.ModelSerializer):
    onboarding_completed = serializers.BooleanField(required=False, write_only=True)

    class Meta:
        model = Profile
        fields = (
            "display_name",
            "avatar_url",
            "preferred_language",
            "bio",
            "country",
            "timezone",
            "onboarding_completed",
        )

    def update(self, instance, validated_data):
        mark_complete = validated_data.pop("onboarding_completed", None)
        profile = super().update(instance, validated_data)
        if mark_complete is True and profile.onboarding_completed_at is None:
            from django.utils import timezone

            profile.onboarding_completed_at = timezone.now()
            profile.save(update_fields=["onboarding_completed_at", "updated_at"])
        elif mark_complete is False:
            profile.onboarding_completed_at = None
            profile.save(update_fields=["onboarding_completed_at", "updated_at"])
        return profile


class UserPreferenceSerializer(serializers.ModelSerializer):
    favorite_genre_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Genre.objects.all(),
        source="favorite_genres",
        required=False,
    )
    favorite_actor_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Actor.objects.all(),
        source="favorite_actors",
        required=False,
    )
    favorite_director_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Director.objects.all(),
        source="favorite_directors",
        required=False,
    )

    class Meta:
        model = UserPreference
        fields = (
            "id",
            "preferred_languages",
            "preferred_decades",
            "favorite_genre_ids",
            "favorite_actor_ids",
            "favorite_director_ids",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_preferred_languages(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Must be a list of language codes.")
        return value

    def validate_preferred_decades(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Must be a list of decades.")
        for decade in value:
            if not isinstance(decade, int) or decade < 1900 or decade > 2100:
                raise serializers.ValidationError(
                    "Each decade must be a valid year between 1900 and 2100."
                )
        return value


class MeSerializer(serializers.Serializer):
    user = UserSerializer(read_only=True)
    profile = ProfileSerializer(read_only=True)
    preferences = UserPreferenceSerializer(read_only=True)

    def to_representation(self, instance: User):
        profile = instance.get_primary_profile()
        preferences = getattr(instance, "preferences", None)
        return {
            "user": UserSerializer(instance).data,
            "profile": ProfileSerializer(profile).data if profile else None,
            "preferences": UserPreferenceSerializer(preferences).data if preferences else None,
        }


def build_token_response(user: User) -> tuple[dict, str]:
    """Return API payload + refresh token string (cookie-only; not included in JSON)."""
    refresh = RefreshToken.for_user(user)
    payload = {
        "access": str(refresh.access_token),
        "user": UserSerializer(user).data,
    }
    return payload, str(refresh)
