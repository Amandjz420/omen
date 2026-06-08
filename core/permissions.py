"""Reusable role-based permissions."""

from __future__ import annotations

from rest_framework.permissions import BasePermission


class RolePermission(BasePermission):
    """Allow access only to users whose role is in ``allowed_roles``.

    Subclass and set ``allowed_roles`` (a set/tuple of role strings). Admins are
    always allowed.
    """

    allowed_roles: tuple[str, ...] = ()

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if getattr(user, "role", None) == "admin" or user.is_superuser:
            return True
        return getattr(user, "role", None) in self.allowed_roles


class IsValuer(RolePermission):
    allowed_roles = ("valuer",)


class IsVerifier(RolePermission):
    allowed_roles = ("verifier",)


class IsValuerOrVerifier(RolePermission):
    allowed_roles = ("valuer", "verifier")
