"""
Root URL configuration.
All API routes are mounted under /api/.
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("accounts.urls")),
    path("api/", include("events.urls")),
]
