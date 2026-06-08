"""Object storage: real S3, or a DB-backed mock that mimics presigned URLs.

Two backends behind one interface, chosen by ``settings.USE_S3``:

* **S3** (creds present): uploads go **browser → S3** via presigned PUT URLs;
  downloads via presigned GET. No bytes pass through Django.
* **DB mock** (no creds — the current setup): bytes are stored in a
  ``StoredBlob`` row (Postgres ``bytea``) so they survive Railway's ephemeral
  filesystem. ``presign_put``/``presign_get`` return signed, time-limited URLs to
  this service's own upload/download endpoints — same 3-step contract as S3
  (presign → PUT → confirm), so the frontend code is identical either way.

The signed token (``django.core.signing``) carries the storage key and the
allowed action, and expires after ``AWS_S3_PRESIGN_EXPIRY`` seconds.
"""

from __future__ import annotations

import uuid
from urllib.parse import urlencode

from django.conf import settings
from django.core import signing

_SALT = "omen.storage"


def build_key(valuation_id, kind: str, filename: str) -> str:
    """Deterministic-ish storage key namespaced by valuation and media kind."""
    safe = filename.replace("/", "_").strip() or "file"
    return f"valuations/{valuation_id}/{kind}/{uuid.uuid4().hex}_{safe}"


# ---------------------------------------------------------------------------
# Signed-URL helpers (DB mock)
# ---------------------------------------------------------------------------
def sign(key: str, action: str) -> str:
    """Sign ``key`` for a given action (``put``/``get``)."""
    return signing.dumps({"k": key, "a": action}, salt=_SALT)


def verify(token: str, action: str) -> str | None:
    """Return the key if ``token`` is a valid, unexpired token for ``action``."""
    try:
        data = signing.loads(token, salt=_SALT, max_age=settings.AWS_S3_PRESIGN_EXPIRY)
    except (signing.BadSignature, signing.SignatureExpired):
        return None
    if data.get("a") != action:
        return None
    return data.get("k")


def _abs(path: str, request) -> str:
    """Build an absolute URL for ``path`` from PUBLIC_BASE_URL or the request."""
    base = (settings.PUBLIC_BASE_URL or "").rstrip("/")
    if not base and request is not None:
        base = f"{request.scheme}://{request.get_host()}"
    return f"{base}{path}"


# ---------------------------------------------------------------------------
# S3 client
# ---------------------------------------------------------------------------
def _s3_client():
    import boto3

    return boto3.client(
        "s3",
        region_name=settings.AWS_S3_REGION_NAME,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )


# ---------------------------------------------------------------------------
# Presign
# ---------------------------------------------------------------------------
def presign_put(key: str, mime: str, *, request=None) -> dict:
    """Return ``{upload_url, headers, method}`` for a direct browser upload."""
    if settings.USE_S3:
        url = _s3_client().generate_presigned_url(
            "put_object",
            Params={
                "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
                "Key": key,
                "ContentType": mime,
            },
            ExpiresIn=settings.AWS_S3_PRESIGN_EXPIRY,
        )
        return {"upload_url": url, "headers": {"Content-Type": mime}, "method": "PUT"}

    qs = urlencode({"token": sign(key, "put")})
    return {
        "upload_url": _abs(f"/api/storage/upload?{qs}", request),
        "headers": {"Content-Type": mime},
        "method": "PUT",
    }


def presign_get(key: str, *, request=None) -> str:
    """Return a time-limited GET URL for a stored object."""
    if settings.USE_S3:
        return _s3_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.AWS_STORAGE_BUCKET_NAME, "Key": key},
            ExpiresIn=settings.AWS_S3_PRESIGN_EXPIRY,
        )
    qs = urlencode({"token": sign(key, "get")})
    return _abs(f"/api/storage/download?{qs}", request)


# ---------------------------------------------------------------------------
# Bytes I/O
# ---------------------------------------------------------------------------
def get_bytes(key: str) -> bytes:
    """Fetch an object's bytes (S3 or DB). Empty bytes if missing."""
    if settings.USE_S3:
        obj = _s3_client().get_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key)
        return obj["Body"].read()
    from .models import StoredBlob

    blob = StoredBlob.objects.filter(key=key).first()
    return bytes(blob.data) if blob else b""


def get_blob(key: str):
    """Return the ``StoredBlob`` for ``key`` (DB backend only), or ``None``."""
    from .models import StoredBlob

    return StoredBlob.objects.filter(key=key).first()


def put_bytes(key: str, data: bytes, mime: str = "application/octet-stream") -> None:
    """Store bytes under ``key`` (S3 object or DB blob)."""
    if settings.USE_S3:
        _s3_client().put_object(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key, Body=data, ContentType=mime
        )
        return
    from .models import StoredBlob

    StoredBlob.objects.update_or_create(
        key=key,
        defaults={"data": data, "content_type": mime, "size": len(data)},
    )
