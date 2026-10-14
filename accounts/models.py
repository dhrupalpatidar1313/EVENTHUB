"""
Custom User model for EventHub.

Extends AbstractUser and adds a `role` field.
AUTH_USER_MODEL must point here before any migration runs.

Roles (TRD §4):
  - attendee  (default) — can reserve seats
  - organizer           — can create/manage events
  - admin               — managed via createsuperuser only
"""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_ATTENDEE = "attendee"
    ROLE_ORGANIZER = "organizer"
    ROLE_ADMIN = "admin"

    ROLE_CHOICES = [
        (ROLE_ATTENDEE, "Attendee"),
        (ROLE_ORGANIZER, "Organizer"),
        (ROLE_ADMIN, "Admin"),
    ]

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_ATTENDEE,
    )
    email = models.EmailField(unique=True)

    # Use email as the identifier for admin login as well
    REQUIRED_FIELDS = ["email"]

    class Meta:
        db_table = "accounts_user"

    def __str__(self):
        return f"{self.username} ({self.role})"

    # ------------------------------------------------------------------
    # Convenience helpers used in permissions
    # ------------------------------------------------------------------
    @property
    def is_organizer(self):
        return self.role == self.ROLE_ORGANIZER

    @property
    def is_attendee(self):
        return self.role == self.ROLE_ATTENDEE

    @property
    def is_admin_role(self):
        """True for users with role='admin' OR Django superusers."""
        return self.role == self.ROLE_ADMIN or self.is_superuser
