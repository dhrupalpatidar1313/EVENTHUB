"""
events/admin.py — Django admin registrations for EventHub models.
"""

from django.contrib import admin
from .models import Category, Event, Reservation, WaitlistEntry


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "slug")


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "date",
        "venue",
        "available_seats",
        "total_seats",
        "price",
        "status",
        "organizer",
        "category",
    )
    list_filter = ("status", "category", "date")
    search_fields = ("title", "venue", "organizer__username")
    readonly_fields = ("created_at",)


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = (
        "booking_code",
        "event",
        "attendee_name",
        "attendee_email",
        "seats_reserved",
        "status",
        "payment_status",
        "created_at",
    )
    list_filter = ("status", "payment_status", "created_at")
    search_fields = ("booking_code", "attendee_name", "attendee_email", "event__title")
    readonly_fields = ("booking_code", "created_at", "cancelled_at")


@admin.register(WaitlistEntry)
class WaitlistEntryAdmin(admin.ModelAdmin):
    list_display = (
        "event",
        "attendee_name",
        "attendee_email",
        "seats_requested",
        "status",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("attendee_name", "attendee_email", "event__title")
    readonly_fields = ("created_at",)
