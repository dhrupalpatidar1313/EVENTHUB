"""
events/urls.py — API route definitions for events, reservations, categories, and waitlist.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CategoryViewSet,
    EventViewSet,
    ReservationViewSet,
    WaitlistEntryViewSet,
)

router = DefaultRouter()
router.register("categories", CategoryViewSet, basename="category")
router.register("events", EventViewSet, basename="event")
router.register("reservations", ReservationViewSet, basename="reservation")
router.register("waitlist", WaitlistEntryViewSet, basename="waitlist")

urlpatterns = [
    path("", include(router.urls)),
]
