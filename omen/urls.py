"""Root URL configuration for the OMEN API."""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)


def health(_request):
    """Liveness probe used by Railway and local smoke tests."""
    return JsonResponse({"status": "ok", "service": "omen-api"})


api_patterns = [
    path("auth/", include("accounts.urls")),
    path("", include("masters.urls")),
    path("", include("leads.urls")),
    path("", include("valuations.urls")),
    path("", include("ai.urls")),
    path("", include("verification.urls")),
    path("", include("reports.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", health, name="health"),
    # OpenAPI schema + Swagger UI
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/", include((api_patterns, "api"))),
]
