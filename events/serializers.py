"""
events/serializers.py — Serializers for EventHub.

Serializers handle cheap early validations and user presentation.
All seat-modifying mutations delegate to services.py inside transaction locks.
"""

from django.utils import timezone
from rest_framework import serializers

from . import services
from .models import Category, Event, Reservation, WaitlistEntry


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug"]


class EventSerializer(serializers.ModelSerializer):
    organizer_name = serializers.CharField(source="organizer.username", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    reservations_count = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "description",
            "venue",
            "date",
            "total_seats",
            "available_seats",
            "price",
            "status",
            "organizer",
            "organizer_name",
            "category",
            "category_name",
            "reservations_count",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "available_seats",
            "organizer",
            "organizer_name",
            "category_name",
            "reservations_count",
            "created_at",
        ]

    def get_reservations_count(self, obj) -> int:
        return obj.reservations.filter(status=Reservation.STATUS_CONFIRMED).count()

    def validate_date(self, value):
        # BR-9: Event date must not be in the past on creation
        if not self.instance and value < timezone.localdate():
            raise serializers.ValidationError("Event date cannot be in the past.")
        return value

    def validate_total_seats(self, value):
        if value < 1:
            raise serializers.ValidationError("Total seats must be at least 1.")
        return value

    def create(self, validated_data):
        user = self.context["request"].user
        validated_data["organizer"] = user
        # BR-10: On creation, available_seats defaults to total_seats
        validated_data["available_seats"] = validated_data["total_seats"]
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # BR-11, BR-12: Total seats change recalculation
        new_total = validated_data.get("total_seats", instance.total_seats)
        if new_total != instance.total_seats:
            booked_seats = instance.total_seats - instance.available_seats
            if new_total < booked_seats:
                raise serializers.ValidationError(
                    {"total_seats": f"Cannot reduce total seats below already booked seats ({booked_seats})."}
                )
            instance.available_seats = new_total - booked_seats

        return super().update(instance, validated_data)


class ReservationSerializer(serializers.ModelSerializer):
    event_title = serializers.CharField(source="event.title", read_only=True)
    user_username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = Reservation
        fields = [
            "id",
            "event",
            "event_title",
            "user",
            "user_username",
            "attendee_name",
            "attendee_email",
            "seats_reserved",
            "status",
            "booking_code",
            "payment_status",
            "cancelled_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "user_username",
            "event_title",
            "status",
            "booking_code",
            "payment_status",
            "cancelled_at",
            "created_at",
        ]

    def validate_seats_reserved(self, value):
        # BR-1: 1 to 5 seats per reservation
        if not 1 <= value <= services.MAX_SEATS_PER_BOOKING:
            raise serializers.ValidationError(
                f"You can reserve 1 to {services.MAX_SEATS_PER_BOOKING} seats per booking."
            )
        return value

    def create(self, validated_data):
        # Delegates directly to locked atomic service
        return services.reserve_seats(
            user=self.context["request"].user,
            event_id=validated_data["event"].pk,
            attendee_name=validated_data["attendee_name"],
            attendee_email=validated_data["attendee_email"],
            seats=validated_data["seats_reserved"],
        )


class WaitlistEntrySerializer(serializers.ModelSerializer):
    event_title = serializers.CharField(source="event.title", read_only=True)

    class Meta:
        model = WaitlistEntry
        fields = [
            "id",
            "event",
            "event_title",
            "user",
            "attendee_name",
            "attendee_email",
            "seats_requested",
            "status",
            "reservation",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "event_title",
            "status",
            "reservation",
            "created_at",
        ]

    def validate_seats_requested(self, value):
        if not 1 <= value <= services.MAX_SEATS_PER_BOOKING:
            raise serializers.ValidationError(
                f"You can request 1 to {services.MAX_SEATS_PER_BOOKING} seats."
            )
        return value

    def create(self, validated_data):
        return services.join_waitlist(
            user=self.context["request"].user,
            event_id=validated_data["event"].pk,
            attendee_name=validated_data["attendee_name"],
            attendee_email=validated_data["attendee_email"],
            seats=validated_data["seats_requested"],
        )
