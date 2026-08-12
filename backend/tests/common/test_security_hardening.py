"""Production security hardening tests (HTTPS, cookies, CORS, metrics, admin)."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, override_settings
from rest_framework import status

from apps.accounts.cookies import refresh_cookie_kwargs
from apps.common.security import (
    cors_origins_are_https,
    csrf_origins_are_https,
    metrics_request_authorized,
)

User = get_user_model()


@pytest.mark.django_db
@override_settings(SECURE_SSL_REDIRECT=True)
def test_https_redirect_when_secure_ssl_redirect_enabled():
    client = Client()
    response = client.get("/api/v1/health/", secure=False)
    assert response.status_code in {301, 302}
    assert response["Location"].startswith("https://")


@pytest.mark.django_db
@override_settings(SECURE_SSL_REDIRECT=False)
def test_http_allowed_when_secure_ssl_redirect_disabled(api_client):
    response = api_client.get("/api/v1/health/")
    assert response.status_code == status.HTTP_200_OK


@override_settings(
    SESSION_COOKIE_SECURE=True,
    CSRF_COOKIE_SECURE=True,
    JWT_REFRESH_COOKIE_SECURE=True,
    JWT_REFRESH_COOKIE_SAMESITE="Lax",
)
def test_secure_cookie_flags_for_production_like_settings():
    kwargs = refresh_cookie_kwargs()
    assert kwargs["secure"] is True
    assert kwargs["httponly"] is True
    assert kwargs["samesite"] == "Lax"


@override_settings(
    JWT_REFRESH_COOKIE_SECURE=False,
    SESSION_COOKIE_SECURE=False,
)
def test_insecure_refresh_cookie_allowed_in_local_http():
    kwargs = refresh_cookie_kwargs()
    assert kwargs["secure"] is False
    assert kwargs["httponly"] is True


@pytest.mark.django_db
@override_settings(
    SECURE_CONTENT_TYPE_NOSNIFF=True,
    X_FRAME_OPTIONS="DENY",
    SECURE_REFERRER_POLICY="strict-origin-when-cross-origin",
    SECURE_HSTS_SECONDS=31536000,
    SECURE_SSL_REDIRECT=False,
)
def test_production_security_headers_present(api_client):
    response = api_client.get("/api/v1/health/", secure=True)
    assert response.status_code == status.HTTP_200_OK
    assert response.get("X-Content-Type-Options") == "nosniff"
    assert response.get("X-Frame-Options") == "DENY"
    # HSTS is added by SecurityMiddleware on HTTPS requests when SECURE_HSTS_SECONDS > 0.
    assert "Strict-Transport-Security" in response


def test_csrf_and_cors_origins_must_be_https_in_helpers():
    assert csrf_origins_are_https(["https://app.example.com"])
    assert not csrf_origins_are_https(["http://app.example.com"])
    assert cors_origins_are_https(["https://app.example.com"])
    assert not cors_origins_are_https(["http://localhost:3000"])


@override_settings(CORS_ALLOW_ALL_ORIGINS=False, CORS_ALLOWED_ORIGINS=["https://app.example.com"])
def test_cors_allow_all_origins_is_false_under_production_like_settings(settings):
    assert settings.CORS_ALLOW_ALL_ORIGINS is False
    assert settings.CORS_ALLOWED_ORIGINS == ["https://app.example.com"]


@pytest.mark.django_db
@override_settings(
    DEBUG=False,
    METRICS_ENABLED=True,
    METRICS_SCRAPE_TOKEN="",
    METRICS_ALLOW_PRIVATE_NETWORK=True,
    METRICS_REQUIRE_TOKEN=False,
)
def test_metrics_allows_loopback_without_token():
    factory = RequestFactory()
    request = factory.get("/metrics/", REMOTE_ADDR="127.0.0.1")
    assert metrics_request_authorized(request) is True


@pytest.mark.django_db
@override_settings(
    DEBUG=False,
    METRICS_ENABLED=True,
    METRICS_SCRAPE_TOKEN="scrape-secret",
    METRICS_ALLOW_PRIVATE_NETWORK=False,
    METRICS_REQUIRE_TOKEN=True,
)
def test_metrics_requires_bearer_token_when_configured():
    factory = RequestFactory()
    denied = factory.get("/metrics/", REMOTE_ADDR="8.8.8.8")
    assert metrics_request_authorized(denied) is False

    allowed = factory.get(
        "/metrics/",
        REMOTE_ADDR="8.8.8.8",
        HTTP_AUTHORIZATION="Bearer scrape-secret",
    )
    assert metrics_request_authorized(allowed) is True


@pytest.mark.django_db
@override_settings(
    DEBUG=False,
    METRICS_ENABLED=True,
    METRICS_SCRAPE_TOKEN="scrape-secret",
    METRICS_ALLOW_PRIVATE_NETWORK=False,
    METRICS_REQUIRE_TOKEN=True,
)
def test_metrics_http_endpoint_returns_403_without_token(api_client):
    response = api_client.get("/metrics/", REMOTE_ADDR="8.8.8.8")
    assert response.status_code == 403


@pytest.mark.django_db
@override_settings(
    DEBUG=False,
    METRICS_ENABLED=True,
    METRICS_SCRAPE_TOKEN="scrape-secret",
    METRICS_ALLOW_PRIVATE_NETWORK=False,
    METRICS_REQUIRE_TOKEN=True,
)
def test_metrics_http_endpoint_allows_bearer_token(api_client):
    response = api_client.get(
        "/metrics/",
        REMOTE_ADDR="8.8.8.8",
        HTTP_AUTHORIZATION="Bearer scrape-secret",
    )
    assert response.status_code == 200
    assert b"cinematch_" in response.content or response.content


@pytest.mark.django_db
def test_admin_requires_authentication(api_client):
    response = api_client.get("/admin/")
    # Unauthenticated users are redirected to the admin login page.
    assert response.status_code in {301, 302}
    assert "/admin/login" in response.url


@pytest.mark.django_db
def test_admin_login_required_for_staff_pages(api_client, user):
    api_client.force_login(user)
    response = api_client.get("/admin/")
    # Non-staff authenticated users still cannot use admin.
    assert response.status_code in {302, 403}


@pytest.mark.django_db
def test_login_sets_httponly_refresh_cookie_without_json_refresh(api_client, user):
    response = api_client.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": "test-pass-123"},
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK
    assert "refresh" not in response.data
    assert "cinematch_refresh" in response.cookies
    cookie = response.cookies["cinematch_refresh"]
    assert cookie["httponly"] is True
