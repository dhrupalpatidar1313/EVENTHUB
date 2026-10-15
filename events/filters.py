"""
events/filters.py — django-filter FilterSets for EventHub.

Supports:
  - Event filtering: status, venue (icontains), category slug/id, date range, has_seats, organizer.
  - Reservation filtering: event_id (from brief), status, payment_status.
"""

from django_filters import rest_framework as filters
from .models import Event, Reservation


class EventFilter(filters.FilterSet):
    venue = filters.CharFilter(field_name="venue", lookup_expr="icontains")
    status = filters.CharFilter(field_name="status", lookup_expr="exact")
    category = filters.CharFilter(method="filter_category")
    date_from = filters.DateFilter(field_name="date", lookup_expr="gte")
    date_to = filters.DateFilter(field_name="date", lookup_expr="lte")
    organizer = filters.NumberFilter(field_name="organizer_id", lookup_expr="exact")
    has_seats = filters.BooleanFilter(method="filter_has_seats")

    class Meta:
        model = Event
        fields = ["venue", "status", "category", "date_from", "date_to", "organizer", "has_seats"]

    def filter_category(self, queryset, name, value):
        if not value:
            return queryset
        if value.isdigit():
            return queryset.filter(category_id=int(value))
        return queryset.filter(category__slug=value)

    def filter_has_seats(self, queryset, name, value):
        if value is True:
            return queryset.filter(available_seats__gt=0)
        elif value is False:
            return queryset.filter(available_seats=0)
        return queryset


class ReservationFilter(filters.FilterSet):
    # From brief: ?event_id=1
    event_id = filters.NumberFilter(field_name="event_id", lookup_expr="exact")
    status = filters.CharFilter(field_name="status", lookup_expr="exact")
    payment_status = filters.CharFilter(field_name="payment_status", lookup_expr="exact")

    class Meta:
        model = Reservation
        fields = ["event_id", "status", "payment_status"]
