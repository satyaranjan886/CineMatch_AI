from django.urls import path

from apps.accounts.views import (
    LoginView,
    LogoutView,
    MeView,
    PreferencesView,
    ProfileView,
    RefreshView,
    RegisterView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="auth-register"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("refresh/", RefreshView.as_view(), name="auth-refresh"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("me/profile/", ProfileView.as_view(), name="auth-profile"),
    path("me/preferences/", PreferencesView.as_view(), name="auth-preferences"),
]
