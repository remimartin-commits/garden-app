from __future__ import annotations

import logging
import uuid
from typing import Iterable
from urllib.parse import unquote, urlparse

from app import config
from app.attachment_utils import (
    attachment_file_urls_removed,
    safe_image_filename,
    storage_canonical_attachment_url,
)

logger = logging.getLogger(__name__)

_CLIENT = None

_ALLOWED_CT = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
        "image/heic",
        "image/heif",
    }
)
_MAX_BYTES = 20 * 1024 * 1024

# Some clients send non-standard ``image/jpg`` or ``application/octet-stream`` for camera JPEGs.
_EXT_TO_MIME = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "jpe": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "gif": "image/gif",
    "heic": "image/heic",
    "heif": "image/heif",
}


def _normalize_image_content_type(content_type: str | None, original_filename: str) -> str:
    raw = (content_type or "").split(";")[0].strip().lower()
    if raw == "image/jpg":
        return "image/jpeg"
    if raw in _ALLOWED_CT:
        return raw
    base = (original_filename or "").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    ext = base.rsplit(".", 1)[-1].lower() if "." in base else ""
    if raw in ("application/octet-stream", "binary/octet-stream", "") and ext in _EXT_TO_MIME:
        return _EXT_TO_MIME[ext]
    return raw


def _s3_client():
    global _CLIENT
    if not config.s3_job_attachments_configured():
        raise RuntimeError("Object storage env vars are not set")
    if _CLIENT is None:
        import boto3
        from botocore.config import Config as BotoConfig

        _CLIENT = boto3.client(
            "s3",
            endpoint_url=config.S3_ENDPOINT_URL,
            aws_access_key_id=config.S3_ACCESS_KEY_ID,
            aws_secret_access_key=config.S3_SECRET_ACCESS_KEY,
            region_name=config.S3_REGION,
            config=BotoConfig(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
    return _CLIENT


def upload_job_image(
    *,
    scope: str,
    scope_id: int,
    original_filename: str,
    content_type: str | None,
    body: bytes,
) -> dict[str, str]:
    """Upload bytes to Hetzner / S3-compatible bucket. Returns ``{filename, file_url}``."""
    if len(body) > _MAX_BYTES:
        raise ValueError(f"File too large (max {_MAX_BYTES // (1024 * 1024)} MB)")
    ct = _normalize_image_content_type(content_type, original_filename)
    if ct not in _ALLOWED_CT:
        raise ValueError(
            "Only image uploads are allowed (JPEG, PNG, WebP, GIF, HEIC). "
            "For JPEG, use a .jpg/.jpeg file or Content-Type image/jpeg."
        )
    ext_fallback = "jpg"
    if "png" in ct:
        ext_fallback = "png"
    elif "webp" in ct:
        ext_fallback = "webp"
    elif "gif" in ct:
        ext_fallback = "gif"
    elif "heic" in ct or "heif" in ct:
        ext_fallback = "heic"

    fname = safe_image_filename(original_filename, ext_fallback)
    key_id = uuid.uuid4().hex
    prefix = config.S3_JOBS_PREFIX.strip().strip("/")
    scope = scope.strip().lower()
    if scope == "recurring":
        key = f"{prefix}/recurring/{int(scope_id)}/{key_id}_{fname}"
    elif scope == "plant":
        key = f"{prefix}/plants/{int(scope_id)}/{key_id}_{fname}"
    elif scope == "customer":
        key = f"{prefix}/customers/{int(scope_id)}/{key_id}_{fname}"
    else:
        key = f"{prefix}/jobs/{int(scope_id)}/{key_id}_{fname}"

    client = _s3_client()
    client.put_object(
        Bucket=config.S3_BUCKET_NAME,
        Key=key,
        Body=body,
        ContentType=ct if ct in _ALLOWED_CT else "image/jpeg",
    )

    base = config.S3_PUBLIC_BASE_URL.rstrip("/")
    if not base:
        raise RuntimeError("S3_PUBLIC_BASE_URL must be set to the public HTTPS base for your bucket")
    public_url = f"{base}/{key}"
    return {"filename": fname, "file_url": public_url}


def attachment_object_key_from_file_url(file_url: str) -> str | None:
    """Recover the S3 object key from the public URL stored at upload (or path suffix for CDNs)."""
    u = (file_url or "").strip()
    if not u:
        return None
    base = config.S3_PUBLIC_BASE_URL.rstrip("/")
    if base and u.startswith(base + "/"):
        key = unquote(u[len(base) + 1 :].lstrip("/"))
        return key or None
    prefix = config.S3_JOBS_PREFIX.strip().strip("/")
    if not prefix:
        return None
    needle = f"{prefix}/"
    try:
        path = unquote(urlparse(u).path or "").lstrip("/")
    except Exception:
        path = ""
    idx = path.find(needle)
    if idx >= 0:
        k = path[idx:]
        return k or None
    return None


def presigned_attachment_get_url(file_url: str, *, expires_seconds: int = 604_800) -> str | None:
    """Signed GET URL so thumbnails work when the bucket is private or the public base is wrong."""
    if not config.s3_job_attachments_configured():
        return None
    key = attachment_object_key_from_file_url(file_url)
    if not key:
        return None
    try:
        client = _s3_client()
        ttl = max(60, min(int(expires_seconds), 604_800))
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": config.S3_BUCKET_NAME, "Key": key},
            ExpiresIn=ttl,
        )
    except Exception:
        return None


def enrich_attachments_for_display(items: list[dict[str, str]] | None) -> list[dict[str, str]]:
    """Copy attachments with ``file_url`` suitable for ``<img src>`` (presigned when possible)."""
    if not items:
        return []
    out: list[dict[str, str]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        fn = str(it.get("filename") or "").strip()
        raw_url = str(it.get("file_url") or "").strip()
        if not fn or not raw_url:
            continue
        signed = presigned_attachment_get_url(raw_url)
        out.append({"filename": fn, "file_url": signed if signed else raw_url})
    return out


def _attachment_key_is_managed(key: str) -> bool:
    prefix = config.S3_JOBS_PREFIX.strip().strip("/")
    if not prefix or not key:
        return False
    return (
        key.startswith(f"{prefix}/jobs/")
        or key.startswith(f"{prefix}/recurring/")
        or key.startswith(f"{prefix}/plants/")
        or key.startswith(f"{prefix}/customers/")
    )


def delete_stored_attachment_object(file_url: str) -> None:
    """Delete the S3 object for a stored attachment URL if it maps to our upload key prefixes. Best-effort."""
    if not config.s3_job_attachments_configured():
        return
    canonical = storage_canonical_attachment_url((file_url or "").strip())
    if not canonical:
        return
    key = attachment_object_key_from_file_url(canonical)
    if not key or not _attachment_key_is_managed(key):
        return
    try:
        _s3_client().delete_object(Bucket=config.S3_BUCKET_NAME, Key=key)
    except Exception:
        logger.warning("delete_object failed for key %s", key, exc_info=True)


def delete_attachments_removed_from_lists(before: list | None, after: list | None) -> None:
    for url in attachment_file_urls_removed(before, after):
        delete_stored_attachment_object(url)


def delete_all_stored_attachments_in_list(items: Iterable | None) -> None:
    if not items:
        return
    for it in items:
        if isinstance(it, dict):
            delete_stored_attachment_object(str(it.get("file_url") or "").strip())
