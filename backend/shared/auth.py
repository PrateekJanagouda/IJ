from django.middleware.csrf import CsrfViewMiddleware
from rest_framework import authentication, exceptions


class SessionAuthentication(authentication.SessionAuthentication):
    """Django session auth that answers 401 (not 403) when credentials are missing.

    DRF returns 403 for unauthenticated session requests because there is no
    WWW-Authenticate scheme. Our API contract distinguishes 401 from 403.
    """

    def authenticate_header(self, request):
        return 'Session realm="api"'


class _CSRFCheck(CsrfViewMiddleware):
    def _reject(self, request, reason):
        return reason


def enforce_csrf(request):
    """Apply CSRF checks to unauthenticated endpoints (login/register) to block login CSRF.

    DRF only enforces CSRF for already-authenticated session requests.
    """
    check = _CSRFCheck(lambda req: None)
    check.process_request(request)
    reason = check.process_view(request, None, (), {})
    if reason:
        raise exceptions.PermissionDenied(f"CSRF failed: {reason}")
