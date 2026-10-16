"""Domain errors and the standard API error envelope (docs/api-and-security.md §2.3)."""

import logging

from django.conf import settings
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions as drf_exceptions
from rest_framework import status
from rest_framework.response import Response

from shared.middleware import get_request_id

logger = logging.getLogger(__name__)


class DomainError(Exception):
    """Raised by domain services. Views never need to translate these by hand."""

    status_code = status.HTTP_400_BAD_REQUEST
    code = "invalid_request"
    message = "The request could not be processed."

    def __init__(self, message=None, *, code=None, details=None):
        self.message = message or self.message
        self.code = code or self.code
        self.details = details or {}
        super().__init__(self.message)


class ValidationFailed(DomainError):
    code = "validation_error"
    message = "The submitted data is invalid."


class Forbidden(DomainError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "permission_denied"
    message = "You do not have permission to perform this action."


class NotFound(DomainError):
    """Also used to conceal private resources the caller may not know exist."""

    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"
    message = "Not found."


class Conflict(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"
    message = "The request conflicts with the current state of the resource."


_DRF_CODES = {
    drf_exceptions.ValidationError: "validation_error",
    drf_exceptions.ParseError: "malformed_request",
    drf_exceptions.NotAuthenticated: "not_authenticated",
    drf_exceptions.AuthenticationFailed: "authentication_failed",
    drf_exceptions.PermissionDenied: "permission_denied",
    drf_exceptions.NotFound: "not_found",
    drf_exceptions.MethodNotAllowed: "method_not_allowed",
    drf_exceptions.UnsupportedMediaType: "unsupported_media_type",
    drf_exceptions.Throttled: "rate_limited",
}


def envelope(code, message, details=None):
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "request_id": get_request_id(),
        }
    }


def exception_handler(exc, context):
    if isinstance(exc, DomainError):
        return Response(envelope(exc.code, exc.message, exc.details), status=exc.status_code)

    if isinstance(exc, Http404):
        exc = drf_exceptions.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = drf_exceptions.PermissionDenied()

    if isinstance(exc, drf_exceptions.APIException):
        code = next(
            (c for cls, c in _DRF_CODES.items() if isinstance(exc, cls)),
            getattr(exc, "default_code", "error"),
        )
        if isinstance(exc, drf_exceptions.ValidationError):
            message, details = "The submitted data is invalid.", {"fields": exc.detail}
        else:
            message, details = str(exc.detail), {}
            if isinstance(exc, drf_exceptions.Throttled) and exc.wait is not None:
                details = {"retry_after_seconds": int(exc.wait)}
        response = Response(envelope(code, message, details), status=exc.status_code)
        if getattr(exc, "auth_header", None):
            response["WWW-Authenticate"] = exc.auth_header
        if getattr(exc, "wait", None) is not None:
            response["Retry-After"] = str(int(exc.wait))
        return response

    if settings.DEBUG:
        return None  # Let Django show the traceback in development and fail loudly in tests.
    # Unexpected error: log with traceback, never leak internals to the client.
    logger.exception("Unhandled API exception")
    return Response(
        envelope("internal_error", "An unexpected error occurred."),
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
