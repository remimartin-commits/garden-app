from __future__ import annotations

from copy import deepcopy
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["pool", "catalog"])

POOL_CONSULTATION_AND_DESIGN_SERVICE = {
    "slug": "consultation-design",
    "status": "published",
    "title": "Pool Consultation & Design",
    "summary": "Early-stage consultation and practical concept design for swimming pool projects.",
    "description": "Our consultation and design stage clarifies site constraints, pool type options, consent considerations, budget ranges, and a realistic installation pathway before committing to construction.",
    "service_type": "Consultation",
    "audiences": ["Homeowners", "Developers"],
    "locations": ["Nationwide New Zealand"],
    "stages": [
        "Site review",
        "Concept layout",
        "Budget guidance",
        "Consent checklist",
    ],
    "coverage": "Nationwide across New Zealand regions.",
    "cta": {"label": "Book a consultation", "href": "/quote"},
}

POOL_DESIGN_AND_INSTALLATION_SERVICE = {
    "slug": "pool-design-and-installation",
    "status": "published",
    "title": "Swimming Pool Design & Installation",
    "summary": "Complete swimming pool design and installation services across New Zealand, from consultation and concept design through excavation, construction, finishing, commissioning, and handover.",
    "description": "Our nationwide pool installation service helps homeowners, developers, and commercial clients understand scope, pricing factors, consent requirements, build timelines, and the practical steps needed to deliver a quality swimming pool.",
    "service_type": "Pool installation",
    "audiences": ["Homeowners", "Developers", "Commercial clients"],
    "locations": ["North Island", "South Island", "Auckland", "Wellington", "Canterbury", "Otago", "Waikato", "Bay of Plenty"],
    "process": [
        {"step": "Consultation", "detail": "Discuss goals, location, site access, pool type, budget range, and ideal timeframe."},
        {"step": "Design and planning", "detail": "Develop a practical pool design and identify engineering, consent, fencing, equipment, and finishing requirements."},
        {"step": "Excavation and preparation", "detail": "Plan access, excavation, base preparation, drainage considerations, and site safety."},
        {"step": "Construction and installation", "detail": "Install the pool structure or shell, plumbing, filtration, circulation, and supporting equipment."},
        {"step": "Finishing and handover", "detail": "Coordinate surrounds, commissioning, water balancing, owner guidance, and final handover."},
    ],
    "pricing_factors": [
        "Pool type, size, and shape",
        "Site access and excavation complexity",
        "Ground conditions and engineering requirements",
        "Council consent and documentation requirements",
        "Heating, covers, filtration, automation, and lighting",
        "Fencing, paving, decking, landscaping, and finishing selections",
        "Regional logistics for nationwide New Zealand projects",
    ],
    "faqs": [
        {
            "question": "How does the pool installation process work?",
            "answer": "We start with consultation and site assessment, then progress through design, pricing, consent planning, excavation, construction or shell installation, equipment setup, finishing, commissioning, and handover.",
        },
        {
            "question": "What affects the cost of a swimming pool?",
            "answer": "Cost is influenced by pool type, size, site conditions, access, engineering, consents, equipment, heating, fencing, paving, landscaping, and regional logistics.",
        },
        {
            "question": "How long will my pool project take?",
            "answer": "Timelines vary depending on design complexity, council consent, site conditions, weather, contractor availability, and the scope of finishing work. We confirm a project-specific schedule after consultation.",
        },
        {
            "question": "Can you help with council consents?",
            "answer": "Yes. We help identify likely council consent and pool safety requirements and coordinate the information needed for applications and compliant handover.",
        },
        {
            "question": "Are your services available nationwide?",
            "answer": "Yes. We support swimming pool installation enquiries across the North Island, South Island, and major New Zealand regions.",
        },
    ],
    "cta": {"label": "Request a Pool Installation Quote", "href": "/quote"},
}

SERVICES = [POOL_CONSULTATION_AND_DESIGN_SERVICE, POOL_DESIGN_AND_INSTALLATION_SERVICE]
POOL_SERVICES = SERVICES


def list_services() -> list[dict]:
    return [deepcopy(service) for service in SERVICES if service.get("status") == "published"]


def get_service(slug: str) -> dict:
    normalized = slug.strip("/").lower()
    for service in SERVICES:
        if service["slug"] == normalized and service.get("status") == "published":
            return deepcopy(service)
    raise HTTPException(status_code=404, detail="Service not found")


def get_service_by_slug(slug: str) -> dict:
    return get_service(slug)


@router.get("/api/services")
def api_list_services() -> dict:
    services = list_services()
    return {"services": services, "items": services, "count": len(services)}


def _service_api_detail(raw: dict[str, Any]) -> dict[str, Any]:
    slim: dict[str, Any] = {
        "slug": raw["slug"],
        "name": raw["title"],
        "description": raw["description"],
    }
    if raw.get("stages"):
        slim["stages"] = list(raw["stages"])
    return slim


@router.get("/api/services/{slug}")
def api_get_service(slug: str) -> dict[str, Any]:
    raw = get_service(slug)
    return {"service": _service_api_detail(raw)}


@router.get("/api/services/{slug}/")
def api_get_service_trailing_slash(slug: str) -> dict:
    return api_get_service(slug)
