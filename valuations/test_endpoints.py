"""End-to-end-ish tests for the valuation flow (mock AI)."""

from __future__ import annotations

import pytest
from django.core.management import call_command
from django.test import override_settings
from rest_framework.test import APIClient

from accounts.models import User
from ai.jobs import process_queued
from valuations.models import Answer, Confidence, Valuation


@pytest.fixture
def seeded(db):
    call_command("seed_demo")
    return Valuation.objects.get(work_order__reference="WO-DEMO-001")


@pytest.fixture
def valuer_client(seeded):
    client = APIClient()
    user = User.objects.get(username="valuer")
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_valuation_list_scoped_to_valuer(valuer_client, seeded):
    resp = valuer_client.get("/api/valuations")
    assert resp.status_code == 200
    refs = [v["work_order_reference"] for v in resp.data["results"]]
    assert "WO-DEMO-001" in refs


@pytest.mark.django_db
def test_detail_merges_questions_with_answers(valuer_client, seeded):
    resp = valuer_client.get(f"/api/valuations/{seeded.id}")
    assert resp.status_code == 200
    assert resp.data["questions"], "case should expose its question set"
    # Before autofill, answers are null.
    assert all(q["answer"] is None for q in resp.data["questions"])


@override_settings(AI_MOCK=True)
@pytest.mark.django_db
def test_autofill_enqueues_job_and_fills_answers(valuer_client, seeded):
    # Enqueue.
    resp = valuer_client.post(f"/api/valuations/{seeded.id}/autofill")
    assert resp.status_code == 202
    job_id = resp.data["job_id"]

    # Process the queue (what the worker does).
    assert process_queued() >= 1

    # Job is done.
    job = valuer_client.get(f"/api/jobs/{job_id}")
    assert job.status_code == 200
    assert job.data["status"] == "done"

    # Answers now exist for every question (mock fills none, so all red rows).
    answers = valuer_client.get(f"/api/valuations/{seeded.id}/answers")
    assert answers.status_code == 200
    assert len(answers.data) == seeded.answers.count()


@pytest.mark.django_db
def test_answer_patch_confirm_clears_red(valuer_client, seeded):
    q = seeded.work_order.service_type.questions.first()
    answer = Answer.objects.create(
        valuation=seeded, question=q, confidence=Confidence.RED
    )
    resp = valuer_client.patch(
        f"/api/answers/{answer.id}",
        {"value": "Ramesh Kumar", "confirmed": True},
        format="json",
    )
    assert resp.status_code == 200
    answer.refresh_from_db()
    assert answer.confirmed is True
    assert answer.confidence == Confidence.GREEN


@pytest.mark.django_db
def test_submit_blocked_by_red_mandatory(valuer_client, seeded):
    # Legacy questions are not mandatory by default; mark one for this scenario.
    q = seeded.work_order.service_type.questions.first()
    q.is_mandatory = True
    q.save(update_fields=["is_mandatory"])
    Answer.objects.create(valuation=seeded, question=q, confidence=Confidence.RED)
    resp = valuer_client.post(f"/api/valuations/{seeded.id}/submit")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_media_presign_and_confirm_flow(valuer_client, seeded):
    presign = valuer_client.post(
        "/api/media/presign",
        {
            "valuation_id": str(seeded.id),
            "kind": "photo",
            "mime": "image/jpeg",
            "filename": "front.jpg",
        },
        format="json",
    )
    assert presign.status_code == 200
    asset_id = presign.data["asset_id"]
    assert presign.data["upload_url"]

    confirm = valuer_client.post(
        "/api/media/confirm",
        {"asset_id": asset_id, "size": 12345, "lat": "12.97", "lng": "77.60"},
        format="json",
    )
    assert confirm.status_code == 200
    assert confirm.data["uploaded"] is True
    # The confirmed asset exposes a (signed) download URL.
    assert confirm.data["download_url"]


@pytest.mark.django_db
def test_db_storage_upload_download_roundtrip(valuer_client, seeded):
    """presign → PUT bytes to the mock-S3 endpoint → download returns them."""
    from urllib.parse import urlparse

    presign = valuer_client.post(
        "/api/media/presign",
        {
            "valuation_id": str(seeded.id),
            "kind": "document",
            "mime": "application/pdf",
            "filename": "deed.pdf",
        },
        format="json",
    )
    assert presign.status_code == 200
    assert presign.data["method"] == "PUT"

    # The browser PUTs the raw bytes straight to the upload_url (no auth header).
    upload_path = urlparse(presign.data["upload_url"]).path
    upload_qs = urlparse(presign.data["upload_url"]).query
    payload = b"%PDF-1.4 fake bytes"
    from rest_framework.test import APIClient

    anon = APIClient()  # presigned token authorizes the write, not a JWT
    put = anon.put(
        f"{upload_path}?{upload_qs}", data=payload, content_type="application/pdf"
    )
    assert put.status_code == 200

    # Confirm, then fetch the signed download URL and check the bytes came back.
    valuer_client.post(
        "/api/media/confirm",
        {"asset_id": presign.data["asset_id"], "size": len(payload)},
        format="json",
    )
    media = valuer_client.get(f"/api/valuations/{seeded.id}/media")
    url = media.data[-1]["download_url"]
    dl = anon.get(urlparse(url).path + "?" + urlparse(url).query)
    assert dl.status_code == 200
    assert dl.content == payload
