import contextvars
import logging
import re
import uuid

_request_id = contextvars.ContextVar("request_id", default=None)
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9_.-]{8,64}$")


def get_request_id():
    return _request_id.get()


class RequestIdMiddleware:
    """Attach a correlation ID to every request, log line, audit record and error body."""

    header = "HTTP_X_REQUEST_ID"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.META.get(self.header, "")
        request_id = incoming if _SAFE_REQUEST_ID.match(incoming) else f"req_{uuid.uuid4().hex}"
        request.request_id = request_id
        token = _request_id.set(request_id)
        try:
            response = self.get_response(request)
        finally:
            _request_id.reset(token)
        response["X-Request-ID"] = request_id
        return response


class RequestIdLogFilter(logging.Filter):
    def filter(self, record):
        record.request_id = get_request_id() or "-"
        return True
