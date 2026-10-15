"""
events/views.py — DRF ViewSets for EventHub.

Endpoints:
  - CategoryViewSet: /api/categories/
  - EventViewSet: /api/events/, /mine/, /{id}/cancel/, /{id}/stats/, /{id}/attendees/, /{id}/waitlist/
  - ReservationViewSet: /api/reservations/, /mine/, /lookup/, /{id}/cancel/, /{id}/pay/
  - WaitlistEntryViewSet: /api/waitlist/, /{id}/
"""

from decimal import Decimal
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from . import services
from .filters import EventFilter, ReservationFilter
from .models import Category, Event, Reservation, WaitlistEntry
from .permissions import (
    IsAdminUserOrReadOnly,
    IsEventOwnerOrAdmin,
    IsOrganizerOrAdmin,
    IsReservationParticipant,
    IsWaitlistOwnerOrAdmin,
)
from .serializers import (
    CategorySerializer,
    EventSerializer,
    ReservationSerializer,
    WaitlistEntrySerializer,
)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminUserOrReadOnly]
    lookup_field = "pk"


class EventViewSet(viewsets.ModelViewSet):
    queryset = Event.objects.select_related("organizer", "category").all()
    serializer_class = EventSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = EventFilter
    search_fields = ["title", "venue", "description"]
    ordering_fields = ["date", "price", "created_at"]
    ordering = ["date"]

    def get_permissions(self):
        if self.action in ("update", "partial_update", "destroy", "cancel"):
            return [IsEventOwnerOrAdmin()]
        elif self.action in ("create",):
            return [IsOrganizerOrAdmin()]
        return [permissions.AllowAny()]

    def destroy(self, request, *args, **kwargs):
        event = self.get_object()
        # BR-13: Event with confirmed reservations cannot be deleted
        if event.reservations.filter(status=Reservation.STATUS_CONFIRMED).exists():
            return Response(
                {"error": "Cannot delete event with confirmed reservations. Cancel it instead."},
                status=status.HTTP_409_CONFLICT,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=["get"], permission_classes=[permissions.IsAuthenticated])
    def mine(self, request):
        """Returns events organized by the currently logged-in user."""
        events = self.get_queryset().filter(organizer=request.user)
        page = self.paginate_queryset(events)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(events, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], permission_classes=[IsEventOwnerOrAdmin])
    def cancel(self, request, pk=None):
        """Cancels event and cascades cancellation to all reservations."""
        event = services.cancel_event(event_id=pk)
        return Response(self.get_serializer(event).data)

    @action(detail=True, methods=["get"], permission_classes=[IsEventOwnerOrAdmin])
    def stats(self, request, pk=None):
        """Returns occupancy, revenue, and reservation metrics for this event."""
        event = self.get_object()
        total_seats = event.total_seats
        seats_sold = total_seats - event.available_seats
        occupancy = round((seats_sold / total_seats * 100), 2) if total_seats > 0 else 0.0

        confirmed_qs = event.reservations.filter(status=Reservation.STATUS_CONFIRMED)
        confirmed_count = confirmed_qs.count()
        cancelled_count = event.reservations.filter(status=Reservation.STATUS_CANCELLED).count()

        total_seats_reserved = confirmed_qs.aggregate(n=Sum("seats_reserved"))["n"] or 0
        revenue = Decimal(total_seats_reserved) * event.price
        waitlist_waiting = event.waitlist.filter(status=WaitlistEntry.STATUS_WAITING).count()

        data = {
            "event": event.pk,
            "total_seats": total_seats,
            "seats_sold": seats_sold,
            "seats_available": event.available_seats,
            "occupancy_percent": occupancy,
            "confirmed_reservations": confirmed_count,
            "cancelled_reservations": cancelled_count,
            "revenue": f"{revenue:.2f}",
            "waitlist_waiting": waitlist_waiting,
        }
        return Response(data)

    @action(detail=True, methods=["get"], permission_classes=[IsEventOwnerOrAdmin])
    def attendees(self, request, pk=None):
        """Lists all confirmed reservations for this event."""
        event = self.get_object()
        reservations = event.reservations.filter(status=Reservation.STATUS_CONFIRMED).select_related("user")
        serializer = ReservationSerializer(reservations, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get", "post"], permission_classes=[permissions.IsAuthenticated])
    def waitlist(self, request, pk=None):
        """
        GET: Lists waiting queue (event organizer or admin).
        POST: Join waitlist for this event (attendee or admin).
        """
        event = self.get_object()
        if request.method == "GET":
            if not (event.organizer == request.user or request.user.is_admin_role):
                return Response({"detail": "Not authorized to view waitlist queue."}, status=status.HTTP_403_FORBIDDEN)
            entries = event.waitlist.filter(status=WaitlistEntry.STATUS_WAITING).order_by("created_at")
            serializer = WaitlistEntrySerializer(entries, many=True)
            return Response(serializer.data)

        # POST: Join waitlist
        serializer = WaitlistEntrySerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        # Note: Event is provided via URL pk
        attendee_name = serializer.validated_data.get("attendee_name") or request.user.get_full_name() or request.user.username
        attendee_email = serializer.validated_data.get("attendee_email") or request.user.email
        seats = serializer.validated_data["seats_requested"]

        entry = services.join_waitlist(
            user=request.user,
            event_id=event.pk,
            attendee_name=attendee_name,
            attendee_email=attendee_email,
            seats=seats,
        )
        return Response(WaitlistEntrySerializer(entry).data, status=status.HTTP_201_CREATED)


class ReservationViewSet(viewsets.ModelViewSet):
    serializer_class = ReservationSerializer
    http_method_names = ["get", "post", "head", "options"]  # BR-19: no PUT, PATCH, DELETE
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = ReservationFilter
    ordering_fields = ["created_at", "seats_reserved"]
    ordering = ["-created_at"]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Reservation.objects.select_related("event", "user")
        if not user.is_authenticated:
            return qs.none()
        if user.is_admin_role:
            return qs.all()
        if user.is_organizer:
            return qs.filter(models_q_organizer_or_user(user))
        return qs.filter(user=user)

    def get_permissions(self):
        if self.action in ("retrieve", "cancel", "pay", "lookup"):
            return [IsReservationParticipant()]
        return [permissions.IsAuthenticated()]

    @action(detail=False, methods=["get"])
    def mine(self, request):
        """Lists reservations made by the logged-in user."""
        reservations = Reservation.objects.filter(user=request.user).select_related("event")
        page = self.paginate_queryset(reservations)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(reservations, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def lookup(self, request):
        """Finds reservation by unique booking code (?code=EH-...)."""
        code = request.query_params.get("code")
        if not code:
            return Response({"error": "Query parameter 'code' is required."}, status=status.HTTP_400_BAD_REQUEST)
        reservation = get_object_or_404(Reservation.objects.select_related("event", "user"), booking_code=code.strip())
        self.check_object_permissions(request, reservation)
        return Response(self.get_serializer(reservation).data)

    @action(detail=True, methods=["post"], permission_classes=[IsReservationParticipant])
    def cancel(self, request, pk=None):
        """Cancels reservation and restores seats."""
        reservation = self.get_object()
        res = services.cancel_reservation(reservation_id=reservation.pk)
        return Response(self.get_serializer(res).data)

    @action(detail=True, methods=["post"], permission_classes=[IsReservationParticipant])
    def pay(self, request, pk=None):
        """Mock payment for pending reservations."""
        reservation = self.get_object()
        res = services.pay_reservation(reservation_id=reservation.pk)
        return Response(self.get_serializer(res).data)


class WaitlistEntryViewSet(viewsets.GenericViewSet):
    serializer_class = WaitlistEntrySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return WaitlistEntry.objects.filter(user=self.request.user).select_related("event")

    def list(self, request):
        entries = self.get_queryset()
        serializer = self.get_serializer(entries, many=True)
        return Response(serializer.data)

    def destroy(self, request, pk=None):
        entry = get_object_or_404(self.get_queryset(), pk=pk)
        entry.status = WaitlistEntry.STATUS_CANCELLED
        entry.save(update_fields=["status"])
        return Response(status=status.HTTP_204_NO_CONTENT)


def models_q_organizer_or_user(user):
    from django.db.models import Q
    return Q(user=user) | Q(event__organizer=user)
