import logging

import redis
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import HttpResponse
from django.views import View
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.observability.metrics import render_metrics

logger = logging.getLogger(__name__)


class LivenessView(APIView):
    """Application liveness — process is up and serving."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []

    def get(self, request):
        return Response(
            {
                "status": "ok",
                "checks": {
                    "application": "ok",
                },
            }
        )


class ReadinessView(APIView):
    """Readiness — application plus dependency probes."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []

    def get(self, request):
        checks = {
            "application": "ok",
            "database": _check_database(),
            "redis": _check_redis(),
        }
        # Back-compat alias used by older monitors / docs.
        checks["cache"] = checks["redis"] if checks["redis"] != "skipped" else _check_cache()

        required = {"application", "database"}
        if getattr(settings, "REDIS_HEALTH_REQUIRED", True):
            required.add("redis")

        healthy = all(checks[name] == "ok" for name in required)
        status_code = 200 if healthy else 503
        return Response(
            {
                "status": "ok" if healthy else "unavailable",
                "checks": checks,
            },
            status=status_code,
        )


class MetricsView(View):
    """Prometheus scrape endpoint — not publicly authorized."""

    http_method_names = ["get", "head", "options"]

    def get(self, request):
        if not getattr(settings, "METRICS_ENABLED", True):
            return HttpResponse("Metrics disabled.", status=404, content_type="text/plain")
        from apps.common.security import metrics_request_authorized

        if not metrics_request_authorized(request):
            return HttpResponse("Forbidden", status=403, content_type="text/plain")
        payload, content_type = render_metrics()
        return HttpResponse(payload, content_type=content_type)


def _check_database() -> str:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return "ok"
    except Exception:
        logger.exception("Readiness database check failed")
        return "error"


def _check_cache() -> str:
    try:
        cache.set("health:ready", "ok", timeout=5)
        if cache.get("health:ready") != "ok":
            return "error"
        return "ok"
    except Exception:
        logger.exception("Readiness cache check failed")
        return "error"


def _check_redis() -> str:
    redis_url = getattr(settings, "REDIS_URL", "") or ""
    if not redis_url:
        return "skipped" if not getattr(settings, "REDIS_HEALTH_REQUIRED", True) else "error"
    try:
        client = redis.from_url(redis_url, socket_connect_timeout=1, socket_timeout=1)
        try:
            if client.ping():
                return "ok"
            return "error"
        finally:
            client.close()
    except Exception:
        logger.exception("Readiness redis check failed")
        if getattr(settings, "REDIS_HEALTH_REQUIRED", True):
            return "error"
        return "skipped"
