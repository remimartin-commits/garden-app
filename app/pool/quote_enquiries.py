from __future__ import annotations

import json
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(tags=["pool", "quote-enquiries"])

_REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = _REPO_ROOT / "data" / "user"
QUOTE_ENQUIRIES_FILE = DATA_DIR / "quote_enquiries.jsonl"
ENQUIRY_LOG = QUOTE_ENQUIRIES_FILE

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

RATE_LIMIT_BUCKET: Dict[str, List[float]] = {}
RATE_LIMIT_MAX_REQUESTS = 100


def _quote_shim() -> Any:
    import app.quote_enquiries as mod

    return mod


def _storage_path(path: Path | None = None) -> Path:
    if path is not None:
        return path
    return _quote_shim().QUOTE_ENQUIRIES_FILE


def _rate_limit_bucket() -> Dict[str, List[float]]:
    shim = _quote_shim()
    bucket = getattr(shim, "_RATE_LIMIT_BUCKET", None)
    if bucket is not None:
        return bucket
    return getattr(shim, "RATE_LIMIT_BUCKET")


def _rate_limit_max_requests() -> int:
    return int(getattr(_quote_shim(), "RATE_LIMIT_MAX_REQUESTS", RATE_LIMIT_MAX_REQUESTS))


def _apply_rate_limit(data: Dict[str, Any]) -> None:
    bucket = _rate_limit_bucket()
    max_req = _rate_limit_max_requests()
    key = _first_text(data, "email", "phone", "name") or "anonymous"
    now = time.time()
    window = 3600.0
    prev = [t for t in bucket.get(key, []) if now - t < window]
    if len(prev) >= max_req:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many submissions from this client; please try again later.",
        )
    prev.append(now)
    bucket[key] = prev


class QuoteEnquiryIn(BaseModel):
    """Inbound quote enquiry payload.

    Keep validation here intentionally lightweight and Pydantic-version-neutral.
    FastAPI deployments for this project may use either Pydantic v1 or v2, and
    previous validator decorators caused import-time failures before endpoint
    tests could run.
    """

    model_config = ConfigDict(extra="allow")

    name: Optional[str] = Field(None, description="Customer or organisation name")
    full_name: Optional[str] = Field(None, description="Alias for name")
    email: Optional[str] = Field(None, description="Customer email address")
    phone: Optional[str] = Field(None, description="Customer phone number")
    location: Optional[str] = Field(None, description="Project city, region, or site location")
    region: Optional[str] = Field(None, description="Alias for location")
    project_location: Optional[str] = Field(None, description="Alias for location")
    client_type: Optional[str] = Field(None, description="homeowner, developer, commercial, etc")
    pool_type: Optional[str] = Field(None, description="fibreglass, concrete, lap pool, commercial, etc")
    project_type: Optional[str] = Field(None, description="new build, renovation, consultation, etc")
    budget: Optional[str] = None
    timeline: Optional[str] = None
    message: Optional[str] = Field(None, description="Project details or consultation request")


class QuoteEnquiryResponse(BaseModel):
    id: str
    status: str
    message: str
    received_at: str


# Backwards-compatible names for imports used elsewhere in the app.
QuoteEnquiry = QuoteEnquiryIn
QuoteEnquiryRequest = QuoteEnquiryIn


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _model_to_dict(payload: Any) -> Dict[str, Any]:
    if hasattr(payload, "model_dump"):
        return payload.model_dump()
    if hasattr(payload, "dict"):
        return payload.dict()
    if isinstance(payload, dict):
        return dict(payload)
    return dict(payload or {})


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _first_text(data: Dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = _clean_text(data.get(key))
        if value:
            return value
    return ""


def _normalise_payload(payload: Any) -> Dict[str, Any]:
    data = _model_to_dict(payload)

    name = _first_text(data, "name", "full_name", "contact_name")
    email = _first_text(data, "email")
    phone = _first_text(data, "phone", "mobile", "telephone")
    location = _first_text(data, "location", "region", "project_location", "site_location", "address")
    message = _first_text(data, "message", "details", "notes", "project_details")

    errors: List[str] = []
    if not name:
        errors.append("name is required")
    if not email and not phone:
        errors.append("email or phone is required")
    if email and not _EMAIL_RE.match(email):
        errors.append("email must be a valid email address")
    if not location:
        location = "Nationwide New Zealand"
    if not message:
        errors.append("message is required")

    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"errors": errors},
        )

    enquiry_id = str(uuid.uuid4())
    received_at = _utc_now()

    normalised: Dict[str, Any] = {
        "id": enquiry_id,
        "received_at": received_at,
        "name": name,
        "email": email,
        "phone": phone,
        "location": location,
        "message": message,
        "client_type": _first_text(data, "client_type"),
        "pool_type": _first_text(data, "pool_type", "poolType"),
        "project_type": _first_text(data, "project_type"),
        "budget": _first_text(data, "budget"),
        "timeline": _first_text(data, "timeline"),
        "source": _first_text(data, "source") or "website",
        "status": "new",
        "state": "new",
    }

    extra = {
        str(k): v
        for k, v in data.items()
        if k not in normalised and v not in (None, "", [], {})
    }
    if extra:
        normalised["extra"] = extra

    return normalised


def save_quote_enquiry(enquiry: Dict[str, Any], path: Path | None = None) -> Dict[str, Any]:
    dest = _storage_path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(enquiry, ensure_ascii=False, sort_keys=True) + "\n")
    return enquiry


def submit_quote_enquiry(payload: Any, *, spam_meta: bool = False) -> Dict[str, Any]:
    enquiry = _normalise_payload(payload)
    enquiry["status"] = "new"
    if spam_meta:
        enquiry["spam_protection"] = {
            "honeypot_checked": True,
            "rate_limit_checked": True,
        }
    return save_quote_enquiry(enquiry)


def list_quote_enquiries(path: Path | None = None) -> List[Dict[str, Any]]:
    target = _storage_path(path)
    if not target.exists():
        return []
    enquiries: List[Dict[str, Any]] = []
    with target.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                enquiries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return enquiries


@router.post(
    "/api/quote-enquiries",
    response_model=QuoteEnquiryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a swimming pool quote enquiry",
)
def create_quote_enquiry(payload: QuoteEnquiryIn = Body(...)) -> QuoteEnquiryResponse:
    raw = _model_to_dict(payload)
    if _clean_text(raw.get("website")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="spam protection triggered",
        )
    _apply_rate_limit(raw)
    enquiry = submit_quote_enquiry(payload, spam_meta=True)
    return QuoteEnquiryResponse(
        id=enquiry["id"],
        status="received",
        message="Thanks, your swimming pool quote enquiry has been received. Our team will be in touch shortly.",
        received_at=enquiry["received_at"],
    )
