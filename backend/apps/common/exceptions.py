import logging

from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def api_exception_handler(exc, context):
    """DRF handler that logs unhandled API exceptions without leaking internals."""
    response = exception_handler(exc, context)
    request = context.get("request")
    request_id = getattr(request, "request_id", "-") if request is not None else "-"

    if response is None:
        logger.exception("Unhandled API exception request_id=%s", request_id)
        return Response(
            {"detail": "Internal server error.", "request_id": request_id},
            status=500,
        )

    if response.status_code >= 500:
        logger.error("API error %s request_id=%s", response.status_code, request_id)
    return response
