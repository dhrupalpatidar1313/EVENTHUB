"""
events/emails.py — Email notifications for EventHub.

All 5 triggers from TRD Section 10:
  1. reservation_confirmed
  2. reservation_cancelled
  3. waitlist_promoted
  4. event_cancelled
  5. waitlist_joined

Always called via transaction.on_commit() to prevent sending emails on rollback.
"""

import logging
from django.conf import settings
from django.core.mail import send_mail
from .models import Reservation, WaitlistEntry

logger = logging.getLogger("events")


def reservation_confirmed(reservation_id: int):
    try:
        res = Reservation.objects.select_related("event").get(pk=reservation_id)
        subject = f"Booking Confirmation: {res.event.title} [{res.booking_code}]"
        message = (
            f"Dear {res.attendee_name},\n\n"
            f"Your booking for '{res.event.title}' is confirmed!\n\n"
            f"Details:\n"
            f"  - Booking Code: {res.booking_code}\n"
            f"  - Venue: {res.event.venue}\n"
            f"  - Date: {res.event.date}\n"
            f"  - Seats Reserved: {res.seats_reserved}\n"
            f"  - Payment Status: {res.payment_status}\n\n"
            f"Thank you for using EventHub!"
        )
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[res.attendee_email],
            fail_silently=True,
        )
        logger.info("Sent reservation confirmation email to %s for booking %s", res.attendee_email, res.booking_code)
    except Exception as e:
        logger.error("Failed sending confirmation email for reservation %s: %s", reservation_id, e)


def reservation_cancelled(reservation_id: int):
    try:
        res = Reservation.objects.select_related("event").get(pk=reservation_id)
        subject = f"Booking Cancelled: {res.event.title} [{res.booking_code}]"
        message = (
            f"Dear {res.attendee_name},\n\n"
            f"Your booking [{res.booking_code}] for '{res.event.title}' has been cancelled.\n"
            f"Seats released: {res.seats_reserved}.\n"
            f"Payment status: {res.payment_status}.\n\n"
            f"We hope to see you at another event soon!"
        )
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[res.attendee_email],
            fail_silently=True,
        )
        logger.info("Sent cancellation email to %s for booking %s", res.attendee_email, res.booking_code)
    except Exception as e:
        logger.error("Failed sending cancellation email for reservation %s: %s", reservation_id, e)


def waitlist_promoted(reservation_id: int):
    try:
        res = Reservation.objects.select_related("event").get(pk=reservation_id)
        subject = f"Great news! You've been promoted from the waitlist for {res.event.title}"
        message = (
            f"Dear {res.attendee_name},\n\n"
            f"Seats became available, and your waitlist entry has been promoted to a confirmed reservation!\n\n"
            f"Details:\n"
            f"  - Event: {res.event.title}\n"
            f"  - Booking Code: {res.booking_code}\n"
            f"  - Venue: {res.event.venue}\n"
            f"  - Date: {res.event.date}\n"
            f"  - Seats: {res.seats_reserved}\n\n"
            f"Please visit EventHub to view or manage your reservation."
        )
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[res.attendee_email],
            fail_silently=True,
        )
        logger.info("Sent waitlist promotion email to %s for booking %s", res.attendee_email, res.booking_code)
    except Exception as e:
        logger.error("Failed sending promotion email for reservation %s: %s", reservation_id, e)


def event_cancelled(reservation_id: int):
    try:
        res = Reservation.objects.select_related("event").get(pk=reservation_id)
        subject = f"Notice: Event Cancelled - {res.event.title}"
        message = (
            f"Dear {res.attendee_name},\n\n"
            f"We regret to inform you that the event '{res.event.title}' scheduled for {res.event.date} at {res.event.venue} has been cancelled by the organizer.\n"
            f"Your reservation [{res.booking_code}] has been cancelled.\n"
            f"Payment status: {res.payment_status}.\n\n"
            f"We apologize for the inconvenience."
        )
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[res.attendee_email],
            fail_silently=True,
        )
        logger.info("Sent event cancellation notice to %s for booking %s", res.attendee_email, res.booking_code)
    except Exception as e:
        logger.error("Failed sending event cancelled email for reservation %s: %s", reservation_id, e)


def waitlist_joined(waitlist_entry_id: int):
    try:
        entry = WaitlistEntry.objects.select_related("event").get(pk=waitlist_entry_id)
        subject = f"Waitlist Confirmation: {entry.event.title}"
        message = (
            f"Dear {entry.attendee_name},\n\n"
            f"You have successfully joined the waitlist for '{entry.event.title}'.\n"
            f"Seats requested: {entry.seats_requested}.\n\n"
            f"We will automatically notify and promote you if seats become available!"
        )
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[entry.attendee_email],
            fail_silently=True,
        )
        logger.info("Sent waitlist joined email to %s for event %s", entry.attendee_email, entry.event.title)
    except Exception as e:
        logger.error("Failed sending waitlist joined email for entry %s: %s", waitlist_entry_id, e)
