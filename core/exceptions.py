"""Consistent API error envelope."""

from __future__ import annotations

from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    """Wrap DRF errors in a stable ``{"error": {...}}`` envelope.

    Keeps response shapes predictable for the Lovable frontend: every handled
    error carries a ``code`` (HTTP status), a ``message``, and the original
    ``detail`` payload.
    """
    response = exception_handler(exc, context)
    if response is None:
        return None

    detail = response.data
    message = "Request failed."
    if isinstance(detail, dict) and "detail" in detail:
        message = str(detail["detail"])
    elif isinstance(detail, list) and detail:
        message = str(detail[0])

    response.data = {
        "error": {
            "code": response.status_code,
            "message": message,
            "detail": detail,
        }
    }
    return response
