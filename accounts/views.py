"""
accounts/views.py  (stub — expanded fully in M4)

Provides the minimal views needed to verify M1:
  POST /api/auth/register/   → 201 Created
  GET  /api/auth/me/         → current user
  PATCH /api/auth/me/        → update name/email
"""

from rest_framework import generics, permissions
from rest_framework.response import Response
from .models import User
from .serializers import RegisterSerializer, UserSerializer


class RegisterView(generics.CreateAPIView):
    """POST /api/auth/register/ — open to anyone."""
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class MeView(generics.RetrieveUpdateAPIView):
    """GET / PATCH /api/auth/me/ — requires authentication."""
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return self.request.user
