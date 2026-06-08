"""Account serializers."""

from __future__ import annotations

from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    """Public representation of a user (no credentials)."""

    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name", "role", "phone")
        read_only_fields = fields


class LoginSerializer(serializers.Serializer):
    """Username/password login payload.

    ``password`` is optional so the DEV_LOGIN path can issue a token for a
    seeded valuer without a password during early frontend integration.
    """

    username = serializers.CharField()
    password = serializers.CharField(required=False, allow_blank=True, write_only=True)
