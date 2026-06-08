"""Auth endpoints: login, refresh, me."""

from __future__ import annotations

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .models import User
from .serializers import LoginSerializer, UserSerializer


def tokens_for(user: User) -> dict:
    """Issue an access/refresh pair plus the serialized user."""
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "user": UserSerializer(user).data,
    }


class LoginView(APIView):
    """``POST /api/auth/login``.

    Standard username/password auth. When ``DEV_LOGIN`` is enabled an empty
    password is accepted for an existing user so the frontend can be wired up
    before OTP/email auth lands.
    """

    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    @extend_schema(request=LoginSerializer, responses=UserSerializer)
    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data["username"]
        password = serializer.validated_data.get("password") or ""

        try:
            user = User.objects.get(username=username, is_active=True)
        except User.DoesNotExist:
            return Response(
                {"detail": "Invalid credentials."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if settings.DEV_LOGIN and not password:
            # Passwordless dev login for the seeded user.
            return Response(tokens_for(user))

        if not user.check_password(password):
            return Response(
                {"detail": "Invalid credentials."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        return Response(tokens_for(user))


class MeView(APIView):
    """``GET /api/auth/me`` — the authenticated user."""

    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    @extend_schema(responses=UserSerializer)
    def get(self, request: Request) -> Response:
        return Response(UserSerializer(request.user).data)


class RefreshView(TokenRefreshView):
    """``POST /api/auth/refresh`` — exchange a refresh token for a new access token."""
