"""
Root URL configuration.
All API routes are mounted under /api/.
Includes OpenAPI Schema and Swagger UI (/api/docs/).
In DEBUG mode, also serves MEDIA_ROOT files (profile pictures, etc.).
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    # OpenAPI 3 Schema & Interactive Documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    # API endpoints
    path("api/", include("accounts.urls")),
    path("api/", include("events.urls")),
]

# Serve uploaded media files in development (DEBUG=True only)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
