"""OpenAPI extensions so the generated contract describes cookie-session auth correctly."""

from drf_spectacular.authentication import SessionScheme


class EQuraSessionScheme(SessionScheme):
    target_class = "shared.auth.SessionAuthentication"
