"""
events/models.py — Data models for EventHub.

Five core models across the project:
  - accounts.User (custom user)
  - Category
  - Event
  - Reservation
  - WaitlistEntry

All constraints use Django 6.x `condition=` syntax.
"""

import secrets
from django.conf import settings
from django.db import models


def generate_booking_code() -> str:
    """Generates a secure, human-readable booking code e.g. EH-3F9A1C07B2"""
    return "EH-" + secrets.token_hex(5).upper()


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)

    class Meta:
        db_table = "events_category"
        verbose_name_plural = "categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Event(models.Model):
    STATUS_UPCOMING = "upcoming"
    STATUS_ONGOING = "ongoing"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_UPCOMING, "Upcoming"),
        (STATUS_ONGOING, "Ongoing"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    venue = models.CharField(max_length=200)
    date = models.DateField()
    total_seats = models.PositiveIntegerField()
    available_seats = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_UPCOMING,
    )
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="organized_events",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "events_event"
        ordering = ["date"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(available_seats__lte=models.F("total_seats")),
                name="event_available_lte_total",
            ),
            models.CheckConstraint(
                condition=models.Q(total_seats__gte=1),
                name="event_total_seats_gte_1",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "date"], name="event_status_date_idx"),
            models.Index(fields=["venue"], name="event_venue_idx"),
            models.Index(fields=["organizer"], name="event_organizer_idx"),
        ]

    def __str__(self):
        return f"{self.title} ({self.date}) - {self.available_seats}/{self.total_seats} seats"


class Reservation(models.Model):
    STATUS_CONFIRMED = "confirmed"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    PAYMENT_PENDING = "pending"
    PAYMENT_PAID = "paid"
    PAYMENT_REFUNDED = "refunded"

    PAYMENT_CHOICES = [
        (PAYMENT_PENDING, "Pending"),
        (PAYMENT_PAID, "Paid"),
        (PAYMENT_REFUNDED, "Refunded"),
    ]

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="reservations",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reservations",
    )
    attendee_name = models.CharField(max_length=200)
    attendee_email = models.EmailField()
    seats_reserved = models.PositiveIntegerField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_CONFIRMED,
    )
    booking_code = models.CharField(
        max_length=16,
        unique=True,
        default=generate_booking_code,
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_CHOICES,
        default=PAYMENT_PENDING,
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "events_reservation"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(seats_reserved__gte=1, seats_reserved__lte=5),
                name="reservation_seats_1_to_5",
            ),
        ]
        indexes = [
            models.Index(fields=["event", "status"], name="res_event_status_idx"),
            models.Index(fields=["user"], name="res_user_idx"),
            models.Index(fields=["booking_code"], name="res_booking_code_idx"),
        ]

    def __str__(self):
        return f"{self.booking_code}: {self.attendee_name} - {self.event.title} ({self.seats_reserved} seats)"


class WaitlistEntry(models.Model):
    STATUS_WAITING = "waiting"
    STATUS_PROMOTED = "promoted"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_WAITING, "Waiting"),
        (STATUS_PROMOTED, "Promoted"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="waitlist",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="waitlist_entries",
    )
    attendee_name = models.CharField(max_length=200)
    attendee_email = models.EmailField()
    seats_requested = models.PositiveIntegerField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_WAITING,
    )
    reservation = models.OneToOneField(
        Reservation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="waitlist_origin",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "events_waitlistentry"
        ordering = ["created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(seats_requested__gte=1, seats_requested__lte=5),
                name="waitlist_seats_1_to_5",
            ),
            models.UniqueConstraint(
                fields=["event", "user"],
                condition=models.Q(status="waiting"),
                name="one_waiting_entry_per_user_event",
            ),
        ]
        indexes = [
            models.Index(fields=["event", "status"], name="waitlist_event_status_idx"),
            models.Index(fields=["user"], name="waitlist_user_idx"),
        ]

    def __str__(self):
        return f"Waitlist: {self.attendee_name} for {self.event.title} ({self.seats_requested} seats, {self.status})"
