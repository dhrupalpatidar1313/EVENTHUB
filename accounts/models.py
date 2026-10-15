"""
Custom User model for EventHub.

Extends AbstractUser and adds:
  - role           (TRD §5)
  - email          (TRD §5, unique)
  - phone_number   (optional profile field)
  - date_of_birth  (optional profile field)
  - profile_picture (optional, ImageField → MEDIA_ROOT/avatars/)
  - street / city / state / country / pincode  (optional address fields)

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

    # ------------------------------------------------------------------ #
    # TRD §5 required fields
    # ------------------------------------------------------------------ #
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_ATTENDEE,
    )
    email = models.EmailField(unique=True)

    # ------------------------------------------------------------------ #
    # Extended profile fields (all optional — null / blank allowed)
    # ------------------------------------------------------------------ #
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text="Contact phone number (optional).",
    )
    date_of_birth = models.DateField(
        null=True,
        blank=True,
        help_text="User's date of birth (optional).",
    )
    profile_picture = models.ImageField(
        upload_to="avatars/",
        null=True,
        blank=True,
        help_text="Profile photo — stored under MEDIA_ROOT/avatars/.",
    )

    # ------------------------------------------------------------------ #
    # Address (split fields for structured storage)
    # ------------------------------------------------------------------ #
    street = models.CharField(max_length=255, blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    state = models.CharField(max_length=100, blank=True, default="")
    country = models.CharField(max_length=100, blank=True, default="")
    pincode = models.CharField(max_length=20, blank=True, default="")

    # Use email as the identifier for admin login as well
    REQUIRED_FIELDS = ["email"]

    class Meta:
        db_table = "accounts_user"

    def __str__(self):
        return f"{self.username} ({self.role})"

    # ------------------------------------------------------------------ #
    # Convenience helpers used in permissions
    # ------------------------------------------------------------------ #
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

    @property
    def full_address(self):
        """Human-readable single-line address (convenience property)."""
        parts = [self.street, self.city, self.state, self.pincode, self.country]
        return ", ".join(p for p in parts if p)
