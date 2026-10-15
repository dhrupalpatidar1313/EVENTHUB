"""
events/permissions.py — Role-based permission classes for EventHub.

Roles:
  - attendee: can view events, reserve seats, join waitlist, view/cancel own bookings.
  - organizer: can create/manage own events, view attendee list, stats, waitlist for their events.
  - admin: can do anything, manage categories.
"""

from rest_framework import permissions


class IsAdminUserOrReadOnly(permissions.BasePermission):
    """Allows full access to Admins, read-only to others (used for Categories)."""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated and request.user.is_admin_role)


class IsOrganizerOrAdmin(permissions.BasePermission):
    """
    Safe methods: public/anyone.
    Write methods (e.g. POST to create events): Organizers or Admins only.
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_organizer or request.user.is_admin_role)
        )


class IsEventOwnerOrAdmin(permissions.BasePermission):
    """
    Object-level permission allowing only the event organizer or platform admin to edit/delete/cancel.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(obj.organizer == request.user or request.user.is_admin_role)


class IsReservationParticipant(permissions.BasePermission):
    """
    Object-level permission:
    A reservation can be viewed/cancelled by:
      - The user who booked it (attendee)
      - The organizer of the event
      - Platform admin
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        return bool(
            obj.user == request.user
            or obj.event.organizer == request.user
            or request.user.is_admin_role
        )


class IsWaitlistOwnerOrAdmin(permissions.BasePermission):
    """
    Object-level permission for waitlist entries:
    Can be viewed/managed by entry owner, event organizer, or admin.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        return bool(
            obj.user == request.user
            or obj.event.organizer == request.user
            or request.user.is_admin_role
        )
