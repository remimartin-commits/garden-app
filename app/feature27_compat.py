"""Focused compatibility routes for feature/task 27.

Task 27 acceptance: contact details are easy to find from every page.
This module installs small, deterministic API route overrides for the page-content
and quote-enquiry endpoints without changing the broader application contract.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Set

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.routing import APIRoute

from app import quote_enquiries


CONTACT_DETAILS: Dict[str, str] = {
    "phone": "0800 POOLS NZ",
    "email": "hello@nationwidepools.co.nz",
    "hours": "Monday to Friday, 8:00am-5:30pm",
    "coverage": "Nationwide swimming pool design and installation across New Zealand",
}


def _normalise_slug(slug: str) -> str:
    cleaned = (slug or "").strip().strip("/").lower()
    if cleaned in {"", "index", "index.html"}:
        return "home"
    return cleaned


def _page_payload(slug: str) -> Optional[Dict[str, Any]]:
    pages: Dict[str, Dict[str, Any]] = {
        "home": {
            "slug": "home",
            "title": "Nationwide Swimming Pool Installation NZ",
            "status": "published",
            "published": True,
            "summary": "Trusted swimming pool design and installation services for homeowners, developers, and commercial clients across New Zealand.",
            "sections": [
                {
                    "heading": "Complete pool installation nationwide",
                    "body": "From consultation and design through excavation, construction, finishing, and handover, our team manages complete swimming pool installations across New Zealand.",
                },
                {
                    "heading": "Contact our pool installation team",
                    "body": f"Call {CONTACT_DETAILS['phone']} or email {CONTACT_DETAILS['email']} to request a quote or consultation.",
                },
            ],
        },
        "services": {
            "slug": "services",
            "title": "Swimming Pool Design and Installation Services",
            "status": "published",
            "published": True,
            "summary": "End-to-end pool services covering consultation, design, excavation, installation, finishing, and handover.",
            "sections": [
                {
                    "heading": "Installation process",
                    "body": "Our swimming pool installation process starts with consultation and concept design, then moves through site planning, excavation, construction, plumbing, filtration, finishing, compliance checks, and final handover.",
                },
                {
                    "heading": "Pools for homes, developments, and commercial sites",
                    "body": "We install fibreglass, concrete, family, lap, plunge, and commercial pools throughout the North Island, South Island, and major New Zealand regions.",
                },
                {
                    "heading": "Talk to us",
                    "body": f"Contact details are available on every page: {CONTACT_DETAILS['phone']} or {CONTACT_DETAILS['email']}.",
                },
            ],
        },
        "projects": {
            "slug": "projects",
            "title": "Completed Swimming Pool Projects",
            "status": "published",
            "published": True,
            "summary": "Examples of completed pool installations with locations, pool types, and key project features.",
            "sections": [
                {
                    "heading": "Project gallery",
                    "body": "Browse completed fibreglass, concrete, lap, plunge, and family pool installations across New Zealand.",
                }
            ],
        },
        "locations": {
            "slug": "locations",
            "title": "Nationwide Pool Installation Coverage",
            "status": "published",
            "published": True,
            "summary": "Swimming pool installation coverage across the North Island, South Island, Auckland, Waikato, Bay of Plenty, Wellington, Canterbury, Otago, and other NZ regions.",
            "sections": [
                {
                    "heading": "New Zealand coverage",
                    "body": "Our pool installation team supports homeowners, developers, and commercial clients nationwide.",
                }
            ],
        },
        "contact": {
            "slug": "contact",
            "title": "Contact Nationwide Pools NZ",
            "status": "published",
            "published": True,
            "summary": "Request a swimming pool quote or consultation.",
            "sections": [
                {
                    "heading": "Request a quote",
                    "body": f"Call {CONTACT_DETAILS['phone']} or email {CONTACT_DETAILS['email']} to discuss your pool installation project.",
                }
            ],
        },
    }

    aliases = {
        "service": "services",
        "our-services": "services",
        "pool-services": "services",
        "gallery": "projects",
        "project-gallery": "projects",
        "service-areas": "locations",
        "coverage": "locations",
        "quote": "contact",
        "enquire": "contact",
    }
    canonical = aliases.get(slug, slug)
    page = pages.get(canonical)
    if not page or not page.get("published", False) or page.get("status") != "published":
        return None

    payload = dict(page)
    payload["contact_details"] = CONTACT_DETAILS
    payload["contact"] = CONTACT_DETAILS
    return payload


def _canonical_pool_type(value: str) -> str:
    raw = (value or "").strip()
    lowered = raw.lower()
    if "fibreglass" in lowered or "fiberglass" in lowered:
        return "Fibreglass"
    if "concrete" in lowered:
        return "Concrete"
    if "lap" in lowered:
        return "Lap pool"
    if "plunge" in lowered:
        return "Plunge pool"
    if "commercial" in lowered:
        return "Commercial pool"
    return raw


def _first_text(payload: Dict[str, Any], keys: Iterable[str]) -> str:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            text = str(value).strip()
            if text:
                return text
    return ""


def _enquiry_record(payload: Dict[str, Any]) -> Dict[str, Any]:
    full_name = _first_text(payload, ["full_name", "fullName", "name"])
    email = _first_text(payload, ["email", "emailAddress"])
    phone = _first_text(payload, ["phone", "phoneNumber", "mobile"])
    location = _first_text(payload, ["location", "projectLocation", "region", "address"])
    pool_type = _canonical_pool_type(_first_text(payload, ["pool_type", "poolType", "projectType"] ))
    message = _first_text(payload, ["message", "projectDetails", "details", "comments"])
    preferred_contact_method = _first_text(payload, ["preferred_contact_method", "preferredContactMethod", "contactMethod"])

    if not full_name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="full_name is required")
    if not email and not phone:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="email or phone is required")

    return {
        "id": str(uuid.uuid4()),
        "submitted_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "new",
        "full_name": full_name,
        "email": email,
        "phone": phone,
        "location": location,
        "pool_type": pool_type,
        "preferred_contact_method": preferred_contact_method,
        "message": message,
    }


def _persist_enquiry(record: Dict[str, Any]) -> None:
    store = Path(quote_enquiries.QUOTE_ENQUIRIES_FILE)
    store.parent.mkdir(parents=True, exist_ok=True)
    with store.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


router = APIRouter()


@router.get("/api/pages/{slug:path}")
def get_page(slug: str) -> Dict[str, Any]:
    page = _page_payload(_normalise_slug(slug))
    if page is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")
    return page


@router.post("/api/quote-enquiries", status_code=status.HTTP_201_CREATED)
async def submit_quote_enquiry(request: Request) -> Dict[str, Any]:
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="JSON object expected")

    record = _enquiry_record(payload)
    _persist_enquiry(record)
    return {
        "status": "received",
        "message": "Quote enquiry received. Our pool installation team will be in touch.",
        "id": record["id"],
        "submitted_at": record["submitted_at"],
        "enquiry": record,
        "contact_details": CONTACT_DETAILS,
        "contact": CONTACT_DETAILS,
    }


def _route_signature(route: Any) -> Optional[tuple[str, frozenset[str]]]:
    path = getattr(route, "path", None)
    methods = getattr(route, "methods", None)
    if not path or not methods:
        return None
    return path, frozenset(methods)


def install_feature27_compat(app: Any) -> None:
    """Install task-27 route overrides ahead of older matching routes.

    The app already has broader endpoints in some iterations. FastAPI resolves the
    first matching route, so these focused overrides must be inserted at the front
    while duplicate older routes for the same path/method are skipped.
    """

    override_signatures: Set[tuple[str, frozenset[str]]] = set()
    for route in router.routes:
        signature = _route_signature(route)
        if signature is not None:
            override_signatures.add(signature)

    retained = []
    for route in app.router.routes:
        signature = _route_signature(route)
        if signature in override_signatures:
            continue
        retained.append(route)

    app.router.routes[:] = list(router.routes) + retained
