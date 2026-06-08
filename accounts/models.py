"""Custom user with valuer/verifier/admin/office roles."""

from __future__ import annotations

import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    VALUER = "valuer", "Valuer"
    VERIFIER = "verifier", "Verifier"
    ADMIN = "admin", "Admin"
    OFFICE = "office", "Office"


class User(AbstractUser):
    """Application user.

    Uses a UUID primary key and a ``role`` field that drives query scoping and
    permissions across the API. OTP/email auth will attach to this model later
    without changing the role model.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.VALUER)
    phone = models.CharField(max_length=20, blank=True)

    def __str__(self) -> str:
        return f"{self.username} ({self.role})"

    @property
    def is_valuer(self) -> bool:
        return self.role == Role.VALUER

    @property
    def is_verifier(self) -> bool:
        return self.role == Role.VERIFIER
