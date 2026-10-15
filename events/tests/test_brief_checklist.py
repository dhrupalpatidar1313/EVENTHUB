"""
events/tests/test_brief_checklist.py

Automated tests directly verifying the 9 brief checklist items:
  1. test_organizer_creates_event (POST /api/events/)
  2. test_list_events_public (GET /api/events/)
  3. test_filter_by_status (GET /api/events/?status=upcoming)
  4. test_filter_by_venue (GET /api/events/?venue=bangalore)
  5. test_reserve_deducts_seats (POST /api/reservations/)
  6. test_overbooking_rejected (400 non_field_errors)
  7. test_cancel_restores_seats (POST /api/reservations/{id}/cancel/)
  8. test_filter_by_event_id (GET /api/reservations/?event_id=...)
  9. test_middleware_logs_request (RequestLoggingMiddleware)
"""

import logging
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from events.models import Event, Reservation

User = get_user_model()


class BriefChecklistTests(APITestCase):
    def setUp(self):
        self.organizer = User.objects.create_user(
            username="org1",
            email="org1@example.com",
            password="Password123!",
            role=User.ROLE_ORGANIZER,
        )
        self.attendee = User.objects.create_user(
            username="att1",
            email="att1@example.com",
            password="Password123!",
            role=User.ROLE_ATTENDEE,
        )
        self.future_date = (timezone.localdate() + timedelta(days=7)).isoformat()

        # Seed an event for read/filter tests
        self.event1 = Event.objects.create(
            title="Bangalore Tech Summit",
            venue="Bangalore International Exhibition Centre",
            date=timezone.localdate() + timedelta(days=10),
            total_seats=100,
            available_seats=100,
            organizer=self.organizer,
            status=Event.STATUS_UPCOMING,
        )
        self.event2 = Event.objects.create(
            title="Mumbai Design Con",
            venue="Mumbai World Trade Center",
            date=timezone.localdate() + timedelta(days=20),
            total_seats=50,
            available_seats=50,
            organizer=self.organizer,
            status=Event.STATUS_COMPLETED,
        )

    def test_1_organizer_creates_event(self):
        """Checklist 1: Organizer can create an event via POST /api/events/."""
        self.client.force_authenticate(user=self.organizer)
        payload = {
            "title": "Django Con 2026",
            "venue": "Bangalore Convention Center",
            "date": self.future_date,
            "total_seats": 200,
            "price": "0.00",
        }
        response = self.client.post("/api/events/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "Django Con 2026")
        self.assertEqual(response.data["available_seats"], 200)
        self.assertEqual(response.data["organizer"], self.organizer.id)

    def test_2_list_events_public(self):
        """Checklist 2: Anyone can list all events via GET /api/events/."""
        # Unauthenticated request
        response = self.client.get("/api/events/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Results can be a list or paginated dict with 'results'
        results = response.data["results"] if "results" in response.data else response.data
        self.assertGreaterEqual(len(results), 2)

    def test_3_filter_by_status(self):
        """Checklist 3: Filter events by status (GET /api/events/?status=upcoming)."""
        response = self.client.get("/api/events/?status=upcoming")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"] if "results" in response.data else response.data
        self.assertTrue(all(e["status"] == "upcoming" for e in results))
        titles = [e["title"] for e in results]
        self.assertIn("Bangalore Tech Summit", titles)
        self.assertNotIn("Mumbai Design Con", titles)

    def test_4_filter_by_venue(self):
        """Checklist 4: Filter events by venue (GET /api/events/?venue=bangalore)."""
        response = self.client.get("/api/events/?venue=bangalore")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"] if "results" in response.data else response.data
        self.assertTrue(all("bangalore" in e["venue"].lower() for e in results))
        titles = [e["title"] for e in results]
        self.assertIn("Bangalore Tech Summit", titles)
        self.assertNotIn("Mumbai Design Con", titles)

    def test_5_reserve_deducts_seats(self):
        """Checklist 5: Creating a reservation deducts available seats."""
        self.client.force_authenticate(user=self.attendee)
        payload = {
            "event": self.event1.id,
            "attendee_name": "Alice Attendee",
            "attendee_email": "alice@example.com",
            "seats_reserved": 3,
        }
        response = self.client.post("/api/reservations/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["seats_reserved"], 3)
        self.assertTrue(response.data["booking_code"].startswith("EH-"))

        # Verify available_seats in database dropped from 100 to 97
        self.event1.refresh_from_db()
        self.assertEqual(self.event1.available_seats, 97)

    def test_6_overbooking_rejected(self):
        """Checklist 6: Overbooking returns 400 with non_field_errors."""
        # Set event with only 2 available seats
        self.event1.available_seats = 2
        self.event1.save()

        self.client.force_authenticate(user=self.attendee)
        payload = {
            "event": self.event1.id,
            "attendee_name": "Alice Attendee",
            "attendee_email": "alice@example.com",
            "seats_reserved": 3,  # Requesting 3 when only 2 are available
        }
        response = self.client.post("/api/reservations/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("non_field_errors", response.data)
        self.assertIn("Only 2 seat(s) available", response.data["non_field_errors"][0])

    def test_7_cancel_restores_seats(self):
        """Checklist 7: Cancelling restores seats and marks status cancelled."""
        self.client.force_authenticate(user=self.attendee)
        res_payload = {
            "event": self.event1.id,
            "attendee_name": "Alice Attendee",
            "attendee_email": "alice@example.com",
            "seats_reserved": 2,
        }
        res_resp = self.client.post("/api/reservations/", res_payload, format="json")
        self.assertEqual(res_resp.status_code, status.HTTP_201_CREATED)
        reservation_id = res_resp.data["id"]

        self.event1.refresh_from_db()
        self.assertEqual(self.event1.available_seats, 98)

        # Cancel the reservation
        cancel_resp = self.client.post(f"/api/reservations/{reservation_id}/cancel/")
        self.assertEqual(cancel_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(cancel_resp.data["status"], "cancelled")

        # Verify seats restored
        self.event1.refresh_from_db()
        self.assertEqual(self.event1.available_seats, 100)

    def test_8_filter_by_event_id(self):
        """Checklist 8: Filter reservations by event_id (GET /api/reservations/?event_id=...)."""
        self.client.force_authenticate(user=self.attendee)
        res1 = self.client.post(
            "/api/reservations/",
            {
                "event": self.event1.id,
                "attendee_name": "User 1",
                "attendee_email": "u1@example.com",
                "seats_reserved": 1,
            },
            format="json",
        )
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)

        response = self.client.get(f"/api/reservations/?event_id={self.event1.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"] if "results" in response.data else response.data
        self.assertTrue(all(r["event"] == self.event1.id for r in results))

    def test_9_middleware_logs_request(self):
        """Checklist 9: RequestLoggingMiddleware logs METHOD, PATH, STATUS."""
        with self.assertLogs("events", level=logging.INFO) as cm:
            response = self.client.get("/api/events/")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(any("GET /api/events/ → 200" in log for log in cm.output))
