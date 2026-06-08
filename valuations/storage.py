"""S3 presign + object access helpers.

Uploads go **browser → S3** via presigned PUT URLs (large audio/photos never
pass through Django). Downloads are served as presigned GET URLs from the
private bucket. When real S3 credentials are absent (local dev/tests),
everything falls back to a local filesystem stub so the upload/confirm/list
flow is still exercisable.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from django.conf import settings


def build_key(valuation_id, kind: str, filename: str) -> str:
    """Deterministic-ish S3 key namespaced by valuation and media kind."""
    safe = filename.replace("/", "_").strip() or "file"
    return f"valuations/{valuation_id}/{kind}/{uuid.uuid4().hex}_{safe}"


def _s3_client():
    import boto3

    return boto3.client(
        "s3",
        region_name=settings.AWS_S3_REGION_NAME,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )


def presign_put(key: str, mime: str) -> dict:
    """Return a presigned PUT URL + headers for a direct browser upload."""
    if not settings.USE_S3:
        # Local stub: the frontend "PUT"s nowhere; confirm just marks uploaded.
        return {
            "upload_url": f"{settings.MEDIA_URL}{key}",
            "headers": {"Content-Type": mime},
            "stub": True,
        }
    url = _s3_client().generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
            "Key": key,
            "ContentType": mime,
        },
        ExpiresIn=settings.AWS_S3_PRESIGN_EXPIRY,
    )
    return {"upload_url": url, "headers": {"Content-Type": mime}, "stub": False}


def presign_get(key: str) -> str:
    """Return a presigned GET URL for a private object (or a local path stub)."""
    if not settings.USE_S3:
        return f"{settings.MEDIA_URL}{key}"
    return _s3_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.AWS_STORAGE_BUCKET_NAME, "Key": key},
        ExpiresIn=settings.AWS_S3_PRESIGN_EXPIRY,
    )


def get_bytes(key: str) -> bytes:
    """Fetch an object's bytes (S3 or local stub). Empty if missing locally."""
    if not settings.USE_S3:
        path = Path(settings.MEDIA_ROOT) / key
        return path.read_bytes() if path.exists() else b""
    obj = _s3_client().get_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key)
    return obj["Body"].read()


def put_bytes(key: str, data: bytes, mime: str = "application/octet-stream") -> None:
    """Store bytes (used by report generation to upload the produced PDF)."""
    if not settings.USE_S3:
        path = Path(settings.MEDIA_ROOT) / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return
    _s3_client().put_object(
        Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key, Body=data, ContentType=mime
    )
