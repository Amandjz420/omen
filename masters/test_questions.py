"""Tests for the question-template endpoint against the real legacy seed.

Verifies the filtering rule from docs/legacy_system_reference.md: filter by
service type + sub type, include questions whose bank_scope is empty OR equals
the requested bank, ordered by detail-category then sequence.
"""

from __future__ import annotations

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from accounts.models import Role, User
from masters.models import Bank, ServiceSubType, ServiceType


@pytest.fixture
def client(db):
    """Load the 904-row legacy seed and return an authenticated client."""
    call_command("seed_from_legacy")
    user = User.objects.create_user(username="q", password="pw12345", role=Role.VALUER)
    api = APIClient()
    api.force_authenticate(user=user)
    return api


def _refs(client):
    st = ServiceType.objects.get(name="Valuation of asset")
    sub = ServiceSubType.objects.get(service_type=st, name="L & B")
    return st, sub


@pytest.mark.django_db
def test_lnb_sbi_returns_unscoped_set_ordered(client):
    st, sub = _refs(client)
    sbi = Bank.objects.get(name="State Bank of India")
    resp = client.get(
        f"/api/questions?service_type={st.id}&sub_type={sub.id}&bank={sbi.id}"
    )
    assert resp.status_code == 200
    data = resp.data
    assert len(data) == 222

    # SBI is not a bank-scoped bank → no bank-specific questions leak in.
    assert all(q["bank"] is None for q in data)

    # Ordered by detail-category sequence, then question sequence.
    keys = [(q["detail_category_sequence"], q["sequence"]) for q in data]
    assert keys == sorted(keys)


@pytest.mark.django_db
def test_bank_scope_adds_only_matching_bank_questions(client):
    st, sub = _refs(client)
    sbi = Bank.objects.get(name="State Bank of India")
    canara = Bank.objects.get(name="Canara Bank")

    sbi_resp = client.get(
        f"/api/questions?service_type={st.id}&sub_type={sub.id}&bank={sbi.id}"
    )
    canara_resp = client.get(
        f"/api/questions?service_type={st.id}&sub_type={sub.id}&bank={canara.id}"
    )

    # Canara gets the unscoped set PLUS its own bank-scoped questions.
    # (resp.data holds raw UUID values pre-JSON, so stringify before comparing.)
    assert len(canara_resp.data) > len(sbi_resp.data)
    canara_id = str(canara.id)
    canara_scoped = [q for q in canara_resp.data if str(q["bank"]) == canara_id]
    assert len(canara_scoped) == 153
    # And none of another bank's scoped questions appear for Canara.
    assert all(
        q["bank"] is None or str(q["bank"]) == canara_id for q in canara_resp.data
    )


@pytest.mark.django_db
def test_no_bank_filter_returns_only_unscoped(client):
    st, sub = _refs(client)
    resp = client.get(f"/api/questions?service_type={st.id}&sub_type={sub.id}")
    assert resp.status_code == 200
    # Without a bank, only bank-agnostic questions are returned.
    assert all(q["bank"] is None for q in resp.data)
    assert len(resp.data) == 222
