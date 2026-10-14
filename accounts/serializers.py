"""
accounts/serializers.py  (stub — filled out fully in M4)

Only the registration serializer is here so M1 can wire a minimal
/api/auth/register/ endpoint and prove the custom User model works.
"""

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from .models import User


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ["id", "username", "email", "password", "role"]
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
    """Read-only representation of the current user (GET /api/auth/me/)."""

    class Meta:
        model = User
        fields = ["id", "username", "email", "role", "first_name", "last_name"]
        read_only_fields = ["id", "role"]
