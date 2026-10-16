from rest_framework.permissions import SAFE_METHODS
from rest_framework.throttling import ScopedRateThrottle


class WriteScopedThrottleMixin:
    """Per-feature (scoped) limits apply to writes only; reads keep the global anon/user
    limits, so list endpoints are still protected against scraping."""

    def get_throttles(self):
        throttles = super().get_throttles()
        if self.request.method in SAFE_METHODS:
            throttles = [t for t in throttles if not isinstance(t, ScopedRateThrottle)]
        return throttles
