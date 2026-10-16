from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

import shared.schema  # noqa: F401  (registers OpenAPI auth extension)
from shared.views import HealthView, ReadinessView

api_v1 = [
    path("health/", HealthView.as_view()),
    path("health/ready/", ReadinessView.as_view()),
    path("", include("apps.identity.urls")),
    path("", include("apps.profiles.urls")),
    path("", include("apps.opportunities.urls")),
    path("", include("apps.social.urls")),
    path("", include("apps.messaging.urls")),
    path("", include("apps.notifications.urls")),
    path("", include("apps.trust_safety.urls")),
]

if settings.EXPOSE_API_DOCS:
    api_v1 += [
        path("schema/", SpectacularAPIView.as_view(), name="schema"),
        path("docs/", SpectacularSwaggerView.as_view(url_name="schema")),
    ]

urlpatterns = [
    path("api/v1/", include(api_v1)),
    path("admin/", admin.site.urls),
]
