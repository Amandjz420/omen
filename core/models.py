"""Shared model primitives."""

from __future__ import annotations

import uuid

from django.db import models


class BaseModel(models.Model):
    """Abstract base with a UUID primary key and created/updated timestamps.

    Every concrete model in OMEN inherits from this so rows are addressable by
    opaque UUIDs (safe to expose in URLs) and carry consistent audit timestamps.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ("-created_at",)
