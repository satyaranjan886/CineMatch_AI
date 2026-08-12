"""Common Django middleware."""

import logging
import time
import uuid
from contextvars import ContextVar

from django.conf import settings
from django.utils.deprecation import MiddlewareMixin

from apps.common.observability.context import endpoint_var, user_id_var
from apps.common.observability.endpoints import normalize_endpoint
from apps.common.observability.metrics import observe_http

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
logger = logging.getLogger("cinematch.request")


class RequestIDMiddleware(MiddlewareMixin):
    """Attach a request ID for log correlation. Honors inbound X-Request-ID."""

    def process_request(self, request):
        incoming = (
            request.META.get("HTTP_X_REQUEST_ID", "").strip()
            or request.META.get("HTTP_X_CORRELATION_ID", "").strip()
        )
        request_id = incoming or uuid.uuid4().hex
        request.request_id = request_id
        request_id_var.set(request_id)

    def process_response(self, request, response):
        request_id = getattr(request, "request_id", request_id_var.get())
        response["X-Request-ID"] = request_id
        return response


class RequestObservabilityMiddleware(MiddlewareMixin):
    """Structured access logs + HTTP Prometheus metrics."""

    def process_request(self, request):
        request._observability_started = time.perf_counter()
        endpoint = normalize_endpoint(request.path)
        request._observability_endpoint = endpoint
        endpoint_var.set(endpoint)

        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            user_id_var.set(str(user.pk))
        else:
            user_id_var.set("-")

    def process_response(self, request, response):
        self._emit(request, response.status_code, error=None)
        return response

    def process_exception(self, request, exception):
        # Still emit a structured log; Django will continue exception handling.
        self._emit(
            request,
            status_code=500,
            error=exception,
        )
        return None

    def _emit(self, request, status_code: int, error: BaseException | None) -> None:
        started = getattr(request, "_observability_started", None)
        if started is None:
            return
        # Avoid double-emitting when both process_exception and process_response run.
        if getattr(request, "_observability_emitted", False):
            return
        request._observability_emitted = True

        latency_seconds = time.perf_counter() - started
        endpoint = getattr(request, "_observability_endpoint", normalize_endpoint(request.path))
        method = request.method.upper()
        user = getattr(request, "user", None)
        user_id = (
            str(user.pk) if user is not None and getattr(user, "is_authenticated", False) else "-"
        )
        user_id_var.set(user_id)
        endpoint_var.set(endpoint)

        observe_http(
            method=method,
            endpoint=endpoint,
            status=status_code,
            latency_seconds=latency_seconds,
        )

        extra = {
            "event": "http_request",
            "method": method,
            "endpoint": endpoint,
            "status": status_code,
            "latency_ms": round(latency_seconds * 1000, 2),
            "user_id": user_id,
        }
        if error is not None:
            extra["error"] = str(error)
            extra["error_type"] = type(error).__name__
            logger.error("request_failed", extra=extra)
        elif status_code >= 500:
            logger.error("request_completed", extra=extra)
        elif status_code >= 400:
            logger.warning("request_completed", extra=extra)
        else:
            logger.info("request_completed", extra=extra)


class SecurityHeadersMiddleware(MiddlewareMixin):
    """Attach CSP and related headers on every response."""

    def process_response(self, request, response):
        csp = getattr(settings, "CONTENT_SECURITY_POLICY", "")
        if csp and "Content-Security-Policy" not in response:
            response["Content-Security-Policy"] = csp
        if "Permissions-Policy" not in response:
            response["Permissions-Policy"] = getattr(
                settings,
                "PERMISSIONS_POLICY",
                "camera=(), microphone=(), geolocation=()",
            )
        if "Cross-Origin-Opener-Policy" not in response:
            response["Cross-Origin-Opener-Policy"] = "same-origin"
        return response
