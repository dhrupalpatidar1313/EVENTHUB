"""
accounts/tests.py — Automated tests for Authentication and User Roles.

Tests:
  - User registration (attendee, organizer)
  - Admin role restriction on self-registration
  - Login / JWT token generation
  - Token refresh
  - Token logout / blacklisting
  - /api/auth/me/ retrieval and profile patching
"""

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class AuthTests(APITestCase):
    def setUp(self):
        self.user_data = {
            "username": "attendee_user",
            "email": "attendee@example.com",
            "password": "StrongPassword123!",
            "role": "attendee",
            "phone_number": "+1234567890",
            "city": "Bengaluru",
        }

    def test_register_attendee(self):
        response = self.client.post("/api/auth/register/", self.user_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["username"], "attendee_user")
        self.assertEqual(response.data["role"], "attendee")
        self.assertEqual(response.data["phone_number"], "+1234567890")
        self.assertEqual(response.data["city"], "Bengaluru")
        self.assertTrue(User.objects.filter(username="attendee_user").exists())

    def test_register_organizer(self):
        data = {
            "username": "organizer_user",
            "email": "organizer@example.com",
            "password": "StrongPassword123!",
            "role": "organizer",
        }
        response = self.client.post("/api/auth/register/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["role"], "organizer")

    def test_register_admin_rejected(self):
        """Admin role cannot be self-registered via public API."""
        data = {
            "username": "hacker_admin",
            "email": "hacker@example.com",
            "password": "StrongPassword123!",
            "role": "admin",
        }
        response = self.client.post("/api/auth/register/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("role", response.data)

    def test_login_and_jwt_tokens(self):
        User.objects.create_user(
            username="jwt_user",
            email="jwt@example.com",
            password="StrongPassword123!",
            role="attendee",
        )
        response = self.client.post(
            "/api/auth/login/",
            {"username": "jwt_user", "password": "StrongPassword123!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_token_refresh(self):
        User.objects.create_user(
            username="refresh_user",
            email="refresh@example.com",
            password="StrongPassword123!",
            role="attendee",
        )
        login_resp = self.client.post(
            "/api/auth/login/",
            {"username": "refresh_user", "password": "StrongPassword123!"},
            format="json",
        )
        refresh_token = login_resp.data["refresh"]

        refresh_resp = self.client.post(
            "/api/auth/token/refresh/",
            {"refresh": refresh_token},
            format="json",
        )
        self.assertEqual(refresh_resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", refresh_resp.data)

    def test_logout_blacklists_token(self):
        User.objects.create_user(
            username="logout_user",
            email="logout@example.com",
            password="StrongPassword123!",
            role="attendee",
        )
        login_resp = self.client.post(
            "/api/auth/login/",
            {"username": "logout_user", "password": "StrongPassword123!"},
            format="json",
        )
        refresh_token = login_resp.data["refresh"]
        access_token = login_resp.data["access"]

        # Logout with refresh token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        logout_resp = self.client.post(
            "/api/auth/logout/",
            {"refresh": refresh_token},
            format="json",
        )
        self.assertEqual(logout_resp.status_code, status.HTTP_200_OK)

        # Attempting to refresh with blacklisted token must fail with 401
        retry_refresh = self.client.post(
            "/api/auth/token/refresh/",
            {"refresh": refresh_token},
            format="json",
        )
        self.assertEqual(retry_refresh.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_endpoint_retrieve_and_patch(self):
        user = User.objects.create_user(
            username="me_user",
            email="me@example.com",
            password="StrongPassword123!",
            role="attendee",
            phone_number="+919876543210",
        )
        self.client.force_authenticate(user=user)

        # GET /api/auth/me/
        get_resp = self.client.get("/api/auth/me/")
        self.assertEqual(get_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(get_resp.data["username"], "me_user")
        self.assertEqual(get_resp.data["phone_number"], "+919876543210")

        # PATCH /api/auth/me/
        patch_resp = self.client.patch(
            "/api/auth/me/",
            {"city": "Hyderabad", "country": "India"},
            format="json",
        )
        self.assertEqual(patch_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_resp.data["city"], "Hyderabad")
        self.assertEqual(patch_resp.data["country"], "India")
