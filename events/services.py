"""
events/services.py — All seat-changing and booking business logic.

Enforces:
  - Row locking with select_for_update() inside transaction.atomic()
  - Zero race conditions on available_seats
  - Maximum 5 seats per reservation (BR-1)
  - Maximum 5 confirmed seats per user per event (BR-2)
  - Event status & date checks (BR-3)
  - Capacity checks (BR-4)
  - Cancellation & refunds (BR-6, BR-7, BR-8)
  - Waitlist joining & FIFO promotion (BR-15, BR-16, BR-17)
  - Event cancellation cascading (BR-14)
"""

from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError

from . import emails
from .models import Event, Reservation, WaitlistEntry

MAX_SEATS_PER_BOOKING = 5
MAX_SEATS_PER_USER_PER_EVENT = 5


class RuleError(APIException):
    status_code = 400


class ConflictError(APIException):
    status_code = 409


def fail(message: str):
    """Raise ValidationError formatted as non_field_errors (matching brief)."""
    raise ValidationError({"non_field_errors": [message]})


def _payment_status_for(event: Event) -> str:
    """Free events are marked 'paid' immediately; paid events start as 'pending'."""
    return Reservation.PAYMENT_PAID if event.price == 0 else Reservation.PAYMENT_PENDING


def _seats_held(event: Event, user) -> int:
    """Calculate how many confirmed seats this user currently holds for the event."""
    if not user or not user.is_authenticated:
        return 0
    total = (
        Reservation.objects.filter(event=event, user=user, status=Reservation.STATUS_CONFIRMED)
        .aggregate(n=Sum("seats_reserved"))["n"]
    )
    return total or 0


@transaction.atomic
def reserve_seats(*, user, event_id: int, attendee_name: str, attendee_email: str, seats: int) -> Reservation:
    """
    Atomic reservation creation with row locking.
    Concurrent bookings for the same event wait on select_for_update().
    """
    event = get_object_or_404(Event.objects.select_for_update(), pk=event_id)

    if event.status not in (Event.STATUS_UPCOMING, Event.STATUS_ONGOING):
        fail(f"Cannot reserve seats for a {event.status} event.")
    if event.date < timezone.localdate():
        fail("This event has already taken place.")
    if not 1 <= seats <= MAX_SEATS_PER_BOOKING:
        fail(f"You can reserve 1 to {MAX_SEATS_PER_BOOKING} seats per booking.")

    held = _seats_held(event, user)
    if held + seats > MAX_SEATS_PER_USER_PER_EVENT:
        fail(f"You can hold at most {MAX_SEATS_PER_USER_PER_EVENT} seats per event ({held} already held).")

    if seats > event.available_seats:
        fail(f"Only {event.available_seats} seat(s) available.")

    event.available_seats -= seats
    event.save(update_fields=["available_seats"])

    reservation = Reservation.objects.create(
        event=event,
        user=user,
        attendee_name=attendee_name,
        attendee_email=attendee_email,
        seats_reserved=seats,
        payment_status=_payment_status_for(event),
    )

    transaction.on_commit(lambda: emails.reservation_confirmed(reservation.pk))
    return reservation


def _cancel(reservation: Reservation, event: Event):
    reservation.status = Reservation.STATUS_CANCELLED
    reservation.cancelled_at = timezone.now()
    if reservation.payment_status == Reservation.PAYMENT_PAID and event.price > 0:
        reservation.payment_status = Reservation.PAYMENT_REFUNDED
    reservation.save(update_fields=["status", "cancelled_at", "payment_status"])


@transaction.atomic
def cancel_reservation(*, reservation_id: int) -> Reservation:
    """
    Cancels a reservation and restores seats, then triggers waitlist promotion.
    Locks event first, then reservation, to guarantee deadlock freedom.
    """
    res_stub = get_object_or_404(Reservation, pk=reservation_id)
    event_id = res_stub.event_id

    # Strict lock order: event first, then reservation
    event = Event.objects.select_for_update().get(pk=event_id)
    reservation = Reservation.objects.select_for_update().get(pk=reservation_id)

    if reservation.status == Reservation.STATUS_CANCELLED:
        raise RuleError({"error": "Already cancelled."})
    if event.status in (Event.STATUS_COMPLETED, Event.STATUS_CANCELLED) or event.date < timezone.localdate():
        raise RuleError({"error": "The event is over, so this can no longer be cancelled."})

    _cancel(reservation, event)
    event.available_seats += reservation.seats_reserved
    promote_waitlist(event)  # promotes oldest eligible waitlist entries & saves event

    transaction.on_commit(lambda: emails.reservation_cancelled(reservation.pk))
    return reservation


def promote_waitlist(event: Event):
    """
    FIFO promotion of waiting entries whose seats_requested fit.
    Must be called with the event row already locked.
    Saves event.available_seats.
    """
    promoted_pks = []
    while event.available_seats > 0:
        entry = (
            WaitlistEntry.objects.select_for_update()
            .filter(event=event, status=WaitlistEntry.STATUS_WAITING, seats_requested__lte=event.available_seats)
            .order_by("created_at", "id")
            .first()
        )
        if entry is None:
            break

        # Check BR-17: if user already reached the 5-seat cap, cancel entry and skip
        if _seats_held(event, entry.user) + entry.seats_requested > MAX_SEATS_PER_USER_PER_EVENT:
            entry.status = WaitlistEntry.STATUS_CANCELLED
            entry.save(update_fields=["status"])
            continue

        reservation = Reservation.objects.create(
            event=event,
            user=entry.user,
            attendee_name=entry.attendee_name,
            attendee_email=entry.attendee_email,
            seats_reserved=entry.seats_requested,
            payment_status=_payment_status_for(event),
        )
        event.available_seats -= entry.seats_requested
        entry.status = WaitlistEntry.STATUS_PROMOTED
        entry.reservation = reservation
        entry.save(update_fields=["status", "reservation"])
        promoted_pks.append(reservation.pk)

    event.save(update_fields=["available_seats"])
    for pk in promoted_pks:
        transaction.on_commit(lambda pk=pk: emails.waitlist_promoted(pk))


@transaction.atomic
def cancel_event(*, event_id: int) -> Event:
    """
    Cancels an event, cascades cancellation to all confirmed reservations with refunds,
    closes all waiting waitlist entries, and restores available_seats.
    """
    event = get_object_or_404(Event.objects.select_for_update(), pk=event_id)
    if event.status == Event.STATUS_CANCELLED:
        raise RuleError({"error": "Event is already cancelled."})

    confirmed_res = list(
        Reservation.objects.select_for_update().filter(event=event, status=Reservation.STATUS_CONFIRMED)
    )
    for r in confirmed_res:
        _cancel(r, event)

    event.waitlist.filter(status=WaitlistEntry.STATUS_WAITING).update(status=WaitlistEntry.STATUS_CANCELLED)
    event.status = Event.STATUS_CANCELLED
    event.available_seats = event.total_seats
    event.save(update_fields=["status", "available_seats"])

    for r in confirmed_res:
        transaction.on_commit(lambda pk=r.pk: emails.event_cancelled(pk))

    return event


@transaction.atomic
def join_waitlist(*, user, event_id: int, attendee_name: str, attendee_email: str, seats: int) -> WaitlistEntry:
    """
    Adds user to waitlist for an event when available_seats cannot accommodate the request (BR-15).
    """
    event = get_object_or_404(Event.objects.select_for_update(), pk=event_id)

    if event.status not in (Event.STATUS_UPCOMING, Event.STATUS_ONGOING):
        fail(f"Cannot join waitlist for a {event.status} event.")
    if event.date < timezone.localdate():
        fail("This event has already taken place.")
    if not 1 <= seats <= MAX_SEATS_PER_BOOKING:
        fail(f"You can request 1 to {MAX_SEATS_PER_BOOKING} seats for waitlist.")

    held = _seats_held(event, user)
    if held + seats > MAX_SEATS_PER_USER_PER_EVENT:
        fail(f"You can hold/request at most {MAX_SEATS_PER_USER_PER_EVENT} seats per event ({held} already held).")

    # Only allowed to join waitlist if event cannot fit requested seats
    if event.available_seats >= seats:
        fail(f"Seats are currently available ({event.available_seats} left). Please make a reservation instead.")

    # Check existing waiting entry for this user
    if WaitlistEntry.objects.filter(event=event, user=user, status=WaitlistEntry.STATUS_WAITING).exists():
        fail("You already have an active waitlist entry for this event.")

    entry = WaitlistEntry.objects.create(
        event=event,
        user=user,
        attendee_name=attendee_name,
        attendee_email=attendee_email,
        seats_requested=seats,
        status=WaitlistEntry.STATUS_WAITING,
    )
    transaction.on_commit(lambda: emails.waitlist_joined(entry.pk))
    return entry


@transaction.atomic
def pay_reservation(*, reservation_id: int) -> Reservation:
    """Mock payment endpoint for pending reservations (BR-18)."""
    res = get_object_or_404(Reservation.objects.select_for_update(), pk=reservation_id)
    if res.status == Reservation.STATUS_CANCELLED:
        raise RuleError({"error": "Cannot pay for a cancelled reservation."})
    if res.payment_status == Reservation.PAYMENT_PAID:
        raise RuleError({"error": "Reservation is already paid."})

    res.payment_status = Reservation.PAYMENT_PAID
    res.save(update_fields=["payment_status"])
    return res
