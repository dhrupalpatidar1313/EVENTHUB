"""
accounts/serializers.py

Serializers for custom User model with profile fields.
"""

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from .models import User


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "password",
            "role",
            "first_name",
            "last_name",
            "phone_number",
            "date_of_birth",
            "street",
            "city",
            "state",
            "country",
            "pincode",
        ]
        read_only_fields = ["id"]

    def validate_role(self, value):
        # Only attendee and organizer are allowed at registration (TRD §4)
        if value not in (User.ROLE_ATTENDEE, User.ROLE_ORGANIZER):
            raise serializers.ValidationError(
                "Role must be 'attendee' or 'organizer'."
            )
        return value

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class UserSerializer(serializers.ModelSerializer):
    """User representation for profile viewing and updating (GET/PATCH /api/auth/me/)."""

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "role",
            "first_name",
            "last_name",
            "phone_number",
            "date_of_birth",
            "profile_picture",
            "street",
            "city",
            "state",
            "country",
            "pincode",
            "full_address",
        ]
        read_only_fields = ["id", "role", "full_address"]
