"""Tests for auth endpoints."""

from __future__ import annotations

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from accounts.models import Role, User


@pytest.fixture
def valuer(db):
    return User.objects.create_user(username="v1", password="pw12345", role=Role.VALUER)


@override_settings(DEV_LOGIN=True)
@pytest.mark.django_db
def test_dev_login_without_password(valuer):
    client = APIClient()
    resp = client.post("/api/auth/login", {"username": "v1"}, format="json")
    assert resp.status_code == 200
    assert "access" in resp.data
    assert resp.data["user"]["role"] == "valuer"


@pytest.mark.django_db
def test_login_with_password(valuer):
    client = APIClient()
    resp = client.post(
        "/api/auth/login", {"username": "v1", "password": "pw12345"}, format="json"
    )
    assert resp.status_code == 200
    assert "access" in resp.data


@pytest.mark.django_db
def test_me_requires_auth_and_returns_user(valuer):
    client = APIClient()
    login = client.post(
        "/api/auth/login", {"username": "v1", "password": "pw12345"}, format="json"
    )
    token = login.data["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.data["username"] == "v1"


@pytest.mark.django_db
def test_me_unauthenticated_rejected():
    assert APIClient().get("/api/auth/me").status_code == 401
