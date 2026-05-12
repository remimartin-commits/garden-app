from __future__ import annotations

import re
from typing import Any


def coerce_attachments_list(raw: Any) -> list[dict[str, str]]:
    """Normalize job/recurring ``attachments`` to ``[{filename, file_url}, ...]``."""
    out: list[dict[str, str]] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        fn = str(item.get("filename") or "").strip()
        url = str(item.get("file_url") or "").strip()
        if fn and url:
            out.append({"filename": fn, "file_url": url})
    return out


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
