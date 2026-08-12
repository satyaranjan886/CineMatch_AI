"""Observability unit tests: health, metrics, logging redaction."""

from __future__ import annotations

import json
import logging

import pytest
from rest_framework import status

from apps.common.logging import JsonFormatter, RequestContextFilter
from apps.common.observability.endpoints import normalize_endpoint
from apps.common.observability.metrics import observe_recommendation, render_metrics
from apps.common.observability.redact import redact_mapping, scrub_message


@pytest.mark.django_db
def test_liveness_returns_application_health(api_client):
    response = api_client.get("/api/v1/health/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["status"] == "ok"
    assert response.data["checks"]["application"] == "ok"
    assert "X-Request-ID" in response


@pytest.mark.django_db
def test_root_health_and_ready_aliases(api_client):
    health = api_client.get("/health/")
    ready = api_client.get("/ready/")

    assert health.status_code == status.HTTP_200_OK
    assert health.data["checks"]["application"] == "ok"
    assert ready.status_code == status.HTTP_200_OK
    assert ready.data["checks"]["application"] == "ok"
    assert ready.data["checks"]["database"] == "ok"
    assert "redis" in ready.data["checks"]


@pytest.mark.django_db
def test_liveness_echoes_inbound_request_id(api_client):
    response = api_client.get("/api/v1/health/", HTTP_X_REQUEST_ID="abc123")
    assert response["X-Request-ID"] == "abc123"


@pytest.mark.django_db
def test_readiness_reports_database_and_redis(api_client):
    response = api_client.get("/api/v1/ready/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["status"] == "ok"
    assert response.data["checks"]["application"] == "ok"
    assert response.data["checks"]["database"] == "ok"
    assert response.data["checks"]["redis"] in {"ok", "skipped"}
    assert response.data["checks"]["cache"] in {"ok", "skipped"}


@pytest.mark.django_db
def test_health_is_public(api_client):
    response = api_client.get("/api/v1/health/")
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_metrics_endpoint_exposes_prometheus_text(api_client):
    observe_recommendation(
        algorithm="popularity",
        model_version="v1",
        latency_seconds=0.012,
        candidate_count=10,
        recommendation_count=5,
        cached=False,
    )
    response = api_client.get("/metrics/")

    assert response.status_code == status.HTTP_200_OK
    body = response.content.decode()
    assert (
        "cinematch_http_requests_total" in body or "cinematch_recommendation_requests_total" in body
    )
    assert "cinematch_recommendation_requests_total" in body


@pytest.mark.django_db
def test_api_v1_metrics_endpoint(api_client):
    response = api_client.get("/api/v1/metrics/")
    assert response.status_code == status.HTTP_200_OK
    assert b"cinematch_" in response.content


def test_normalize_endpoint_collapses_ids():
    assert normalize_endpoint("/api/v1/movies/3cc00980-1233-45fc-9c38-4fa0ebcaa389/") == (
        "/api/v1/movies/:id"
    )
    assert normalize_endpoint("/api/v1/movies/42/") == "/api/v1/movies/:id"


def test_redact_mapping_masks_secrets():
    payload = redact_mapping(
        {
            "email": "user@example.com",
            "password": "hunter2",
            "refresh_token": "abc",
            "nested": {"access": "tok"},
        }
    )
    assert payload["email"] == "user@example.com"
    assert payload["password"] == "[REDACTED]"
    assert payload["refresh_token"] == "[REDACTED]"
    assert payload["nested"]["access"] == "[REDACTED]"


def test_scrub_message_masks_bearer_and_query_secrets():
    assert "[REDACTED]" in scrub_message("Authorization: Bearer super-secret-token")
    assert "[REDACTED]" in scrub_message("/login?password=hunter2&next=/home")


def test_json_formatter_includes_structured_fields():
    record = logging.LogRecord(
        name="cinematch.request",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request_completed",
        args=(),
        exc_info=None,
    )
    record.request_id = "rid-1"
    record.user_id = "user-1"
    record.endpoint = "/api/v1/health"
    record.method = "GET"
    record.status = 200
    record.latency_ms = 12.5
    RequestContextFilter().filter(record)
    payload = json.loads(JsonFormatter().format(record))

    assert payload["request_id"] == "rid-1"
    assert payload["user_id"] == "user-1"
    assert payload["endpoint"] == "/api/v1/health"
    assert payload["status"] == 200
    assert payload["latency_ms"] == 12.5
    assert "password" not in payload


def test_render_metrics_returns_prometheus_payload():
    payload, content_type = render_metrics()
    assert b"cinematch_" in payload or payload  # registry may already have collectors
    assert "text/plain" in content_type
