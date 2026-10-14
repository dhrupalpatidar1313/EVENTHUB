"""
events/urls.py  (M1 stub — routes added in M2)
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
# ViewSets registered in M2

urlpatterns = [
    path("", include(router.urls)),
]
