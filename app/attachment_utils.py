from __future__ import annotations

import re
from typing import Any


def storage_canonical_attachment_url(url: str) -> str:
    """Drop presigned GET query string so PATCH round-trips after API returns signed URLs."""
    u = (url or "").strip()
    if not u or "?" not in u:
        return u
    q = u.split("?", 1)[1]
    if "X-Amz-Algorithm" in q or "X-Amz-Signature" in q:
        return u.split("?", 1)[0]
    return u


def coerce_attachments_list(raw: Any) -> list[dict[str, str]]:
    """Normalize job/recurring ``attachments`` to ``[{filename, file_url}, ...]``."""
    out: list[dict[str, str]] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        fn = str(item.get("filename") or "").strip()
        url = storage_canonical_attachment_url(str(item.get("file_url") or "").strip())
        if fn and url:
            out.append({"filename": fn, "file_url": url})
    return out


def attachment_file_urls_coerced(items: Any) -> set[str]:
    """Set of canonical ``file_url`` strings from an attachment list (any invalid entries skipped)."""
    urls: set[str] = set()
    if not isinstance(items, list):
        return urls
    for it in items:
        if not isinstance(it, dict):
            continue
        u = storage_canonical_attachment_url(str(it.get("file_url") or "").strip())
        if u:
            urls.add(u)
    return urls


def attachment_file_urls_removed(before_items: Any, after_items: Any) -> list[str]:
    """``file_url`` values present in ``before`` but not in ``after`` (e.g. after PATCH removes photos)."""
    return list(attachment_file_urls_coerced(before_items) - attachment_file_urls_coerced(after_items))


def safe_image_filename(original: str, fallback_ext: str) -> str:
    base = original.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if "." in base:
        stem, ext = base.rsplit(".", 1)
    else:
        stem, ext = base, ""
    stem = re.sub(r"[^a-zA-Z0-9_-]+", "_", stem).strip("._") or "photo"
    ext_clean = re.sub(r"[^a-zA-Z0-9]", "", (ext or fallback_ext).lower())[:8]
    if ext_clean not in ("jpg", "jpeg", "png", "webp", "gif", "heic"):
        ext_clean = "jpg"
    if ext_clean == "jpeg":
        ext_clean = "jpg"
    return f"{stem[:72]}.{ext_clean}"
