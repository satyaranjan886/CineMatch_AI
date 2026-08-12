from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from apps.accounts.forms import UserChangeForm, UserCreationForm
from apps.accounts.models import Profile, User, UserPreference


class ProfileInline(admin.TabularInline):
    model = Profile
    extra = 0
    fields = ("display_name", "is_primary", "preferred_language", "onboarding_completed_at")
    readonly_fields = ("created_at", "updated_at")


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "is_staff", "is_active", "date_joined")
    search_fields = ("email", "first_name", "last_name")
    list_filter = ("is_staff", "is_superuser", "is_active")
    readonly_fields = ("last_login", "date_joined")
    inlines = (ProfileInline,)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal", {"fields": ("first_name", "last_name")}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2", "is_staff", "is_superuser"),
            },
        ),
    )
    filter_horizontal = ("groups", "user_permissions")


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "display_name",
        "is_primary",
        "preferred_language",
        "country",
        "onboarding_completed_at",
        "created_at",
    )
    search_fields = ("user__email", "display_name")
    list_filter = ("is_primary", "preferred_language", "country")
    readonly_fields = ("created_at", "updated_at")


@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "updated_at")
    search_fields = ("user__email",)
    filter_horizontal = ("favorite_genres", "favorite_actors", "favorite_directors")
    readonly_fields = ("created_at", "updated_at")
