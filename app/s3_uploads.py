from __future__ import annotations

import uuid

from app import config

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

    from app.attachment_utils import safe_image_filename

    fname = safe_image_filename(original_filename, ext_fallback)
    key_id = uuid.uuid4().hex
    prefix = config.S3_JOBS_PREFIX.strip().strip("/")
    scope = scope.strip().lower()
    if scope == "recurring":
        key = f"{prefix}/recurring/{int(scope_id)}/{key_id}_{fname}"
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
