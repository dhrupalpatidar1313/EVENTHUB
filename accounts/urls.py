"""
accounts/urls.py

Auth routes under /api/auth/ (TRD §8):
  POST   /api/auth/register/       → create account
  POST   /api/auth/login/          → obtain JWT pair
  POST   /api/auth/token/refresh/  → refresh access token
  POST   /api/auth/logout/         → blacklist refresh token
  GET    /api/auth/me/             → current user
  PATCH  /api/auth/me/             → update name/email
"""

from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenBlacklistView,
)
from .views import RegisterView, MeView

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/login/", TokenObtainPairView.as_view(), name="auth-login"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="auth-token-refresh"),
    path("auth/logout/", TokenBlacklistView.as_view(), name="auth-logout"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
]
