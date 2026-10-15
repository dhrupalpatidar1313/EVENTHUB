"""
accounts/admin.py — Register custom User in Django admin.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "role", "phone_number", "is_staff", "is_active")
    list_filter = ("role", "is_staff", "is_active")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("EventHub role", {"fields": ("role",)}),
        (
            "Profile Information",
            {
                "fields": (
                    "phone_number",
                    "date_of_birth",
                    "profile_picture",
                    "street",
                    "city",
                    "state",
                    "country",
                    "pincode",
                )
            },
        ),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("EventHub role", {"fields": ("role",)}),
        (
            "Profile Information",
            {
                "fields": (
                    "phone_number",
                    "date_of_birth",
                    "profile_picture",
                    "street",
                    "city",
                    "state",
                    "country",
                    "pincode",
                )
            },
        ),
    )
    search_fields = ("username", "email", "phone_number", "city")
    ordering = ("username",)
