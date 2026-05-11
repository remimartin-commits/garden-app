from __future__ import annotations

from copy import deepcopy
from typing import Any


def normalise_slug(value: str) -> str:
    return str(value or "").strip().strip("/").lower()


FAQS: list[dict[str, Any]] = [
    {
        "question": "What is included in the swimming pool installation process?",
        "answer": "Our complete installation process covers consultation, site assessment, concept design, engineering coordination, council consent guidance, excavation, pool construction, filtration setup, surrounds, finishing, compliance checks, and handover.",
    },
    {
        "question": "What pricing factors affect a new swimming pool in New Zealand?",
        "answer": "Pool pricing depends on pool type, size, site access, excavation conditions, engineering requirements, finishes, heating, covers, landscaping, fencing, drainage, and council consent requirements.",
    },
    {
        "question": "How long does a pool installation usually take?",
        "answer": "Most residential pool projects take several weeks once consent and final selections are complete. Timelines vary by pool type, site complexity, weather, council processing, and finishing scope.",
    },
    {
        "question": "Do swimming pools need council consent?",
        "answer": "Many New Zealand swimming pool projects require building consent, pool barrier compliance, inspections, and sometimes resource planning checks. We explain the likely consent pathway during consultation.",
    },
    {
        "question": "Do you install pools nationwide?",
        "answer": "Yes. We support swimming pool design and installation enquiries across New Zealand, including the North Island, South Island, Auckland, Waikato, Bay of Plenty, Wellington, Canterbury, Otago, and other regional locations.",
    },
]

INSTALLATION_PROCESS = [
    {
        "step": "Consultation and site assessment",
        "description": "We confirm goals, location, access, budget range, pool use, and site constraints before recommending the best installation pathway.",
    },
    {
        "step": "Design, specification, and consent planning",
        "description": "Pool type, layout, finishes, filtration, heating, safety barriers, drainage, and council consent requirements are planned before construction starts.",
    },
    {
        "step": "Excavation and construction",
        "description": "The site is set out, excavated, prepared, and built using the selected fibreglass or concrete pool system with coordinated trades.",
    },
    {
        "step": "Finishing and commissioning",
        "description": "Surrounds, coping, fencing coordination, equipment commissioning, water balancing, compliance checks, and handover are completed.",
    },
]

SERVICES: list[dict[str, Any]] = [
    {
        "slug": "complete-pool-installation",
        "title": "Complete Swimming Pool Installation",
        "service_name": "Complete Swimming Pool Installation",
        "summary": "Nationwide swimming pool consultation, design, excavation, construction, finishing, and handover for New Zealand homes, developments, and commercial sites.",
        "description": "A complete pool installation service from first consultation through to finished handover, with practical guidance on pool type, pricing factors, timelines, council consents, and site constraints.",
        "pool_types": ["Fibreglass", "Concrete", "Lap pool", "Family pool", "Commercial pool"],
        "installation_process": INSTALLATION_PROCESS,
        "process": INSTALLATION_PROCESS,
        "pricing_factors": [
            "Pool type and size",
            "Site access and excavation complexity",
            "Ground conditions and engineering requirements",
            "Finishes, surrounds, heating, covers, and landscaping",
            "Council consent, inspections, and pool barrier compliance",
        ],
        "timelines": "Typical installation timeframes depend on pool type, site access, weather, trade availability, and council consent processing.",
        "council_consents": "We help clients understand likely building consent, inspection, drainage, and pool barrier obligations for their local council area.",
        "nationwide_availability": "Available for enquiries across New Zealand, including the North Island, South Island, and major regions.",
        "cta": "Request a swimming pool quote or book a consultation",
        "faqs": FAQS,
    }
]

PROJECTS: list[dict[str, Any]] = [
    {
        "slug": "tauranga-family-fibreglass-pool",
        "title": "Tauranga Family Fibreglass Pool",
        "location": "Tauranga, Bay of Plenty",
        "region": "Bay of Plenty",
        "pool_type": "Fibreglass",
        "client_type": "Homeowner",
        "image": "/static/images/projects/tauranga-family-fibreglass-pool.jpg",
        "images": ["/static/images/projects/tauranga-family-fibreglass-pool.jpg"],
        "features": ["Family recreation", "Low-maintenance fibreglass shell", "Integrated filtration", "Safety barrier coordination"],
        "summary": "A family-focused fibreglass pool installation designed for relaxed outdoor living in Tauranga.",
        "case_study": {
            "challenge": "Create a durable family pool with clear access planning and minimal maintenance.",
            "solution": "A fibreglass pool package with coordinated excavation, filtration, surrounds, and handover guidance.",
            "outcome": "A practical backyard pool ready for everyday family use.",
        },
    },
    {
        "slug": "queenstown-concrete-lap-pool",
        "title": "Queenstown Concrete Lap Pool",
        "location": "Queenstown, Otago",
        "region": "Otago",
        "pool_type": "Concrete",
        "client_type": "Commercial accommodation",
        "image": "/static/images/projects/queenstown-concrete-lap-pool.jpg",
        "images": ["/static/images/projects/queenstown-concrete-lap-pool.jpg"],
        "features": ["Concrete lap pool", "Commercial guest use", "Heating allowance", "Mountain-site planning"],
        "summary": "A concrete lap pool case study for a lodge-style commercial accommodation setting.",
        "case_study": {
            "challenge": "Deliver a refined pool experience for guests while managing site and climate constraints.",
            "solution": "A concrete lap pool design with robust equipment selection and staged construction planning.",
            "outcome": "A premium pool amenity suited to year-round visitor expectations.",
        },
    },
    {
        "slug": "auckland-entertainer-pool",
        "title": "Auckland Entertainer Pool",
        "location": "Auckland",
        "region": "Auckland",
        "pool_type": "Fibreglass",
        "client_type": "Homeowner",
        "image": "/static/images/projects/auckland-entertainer-pool.jpg",
        "images": ["/static/images/projects/auckland-entertainer-pool.jpg"],
        "features": ["Entertainment area", "Pool lighting", "Heating", "Finished surrounds"],
        "summary": "A compact entertainer pool for an Auckland backyard renovation.",
        "case_study": {
            "challenge": "Fit a usable pool into a constrained urban backyard.",
            "solution": "A compact fibreglass pool with careful access planning and integrated outdoor living finishes.",
            "outcome": "A high-use entertainment space with clear quote and handover documentation.",
        },
    },
]

# Common aliases used by older tests and frontend routes.
PROJECT_ALIASES = {
    "waikato-family-fibreglass-pool": "tauranga-family-fibreglass-pool",
    "auckland-family-fibreglass-pool": "auckland-entertainer-pool",
    "queenstown-lodge-concrete-lap-pool": "queenstown-concrete-lap-pool",
}

SERVICE_AREAS: list[dict[str, Any]] = [
    {
        "slug": "nationwide",
        "name": "Nationwide New Zealand",
        "region": "New Zealand",
        "title": "Nationwide Swimming Pool Installation Coverage",
        "summary": "Swimming pool design and installation enquiries are supported nationwide across New Zealand.",
        "coverage_notes": "We assist homeowners, developers, and commercial clients across the North Island, South Island, and major New Zealand regions.",
        "locations": ["North Island", "South Island", "Auckland", "Waikato", "Bay of Plenty", "Wellington", "Canterbury", "Otago"],
        "services": ["Consultation", "Design", "Excavation", "Construction", "Finishing", "Handover"],
        "service_available": True,
        "lead_generation_title": "Request a nationwide pool installation quote",
        "quote_cta": "Request a quote for your New Zealand pool project",
        "consultation_cta": "Book a consultation with our pool installation team",
        "href": "/service-areas/nationwide",
        "phone": "0800 POOL NZ",
        "email": "quotes@example.co.nz",
    },
    {
        "slug": "north-island",
        "name": "North Island",
        "region": "North Island",
        "title": "North Island Pool Installation",
        "summary": "Pool installation consultation, design, and construction support across North Island locations.",
        "coverage_notes": "Coverage includes Auckland, Waikato, Bay of Plenty, Wellington, and surrounding areas.",
        "locations": ["Auckland", "Waikato", "Bay of Plenty", "Wellington"],
        "services": ["Consultation", "Design", "Excavation", "Construction", "Handover"],
        "service_available": True,
        "lead_generation_title": "North Island swimming pool quotes",
        "quote_cta": "Request a North Island pool quote",
        "consultation_cta": "Book a North Island consultation",
        "href": "/service-areas/north-island",
        "phone": "0800 POOL NZ",
        "email": "quotes@example.co.nz",
    },
    {
        "slug": "south-island",
        "name": "South Island",
        "region": "South Island",
        "title": "South Island Pool Installation",
        "summary": "Swimming pool design and installation enquiries for South Island homes, lodges, and commercial projects.",
        "coverage_notes": "Coverage includes Canterbury, Otago, Queenstown Lakes, Nelson, Marlborough, and surrounding regions.",
        "locations": ["Canterbury", "Otago", "Queenstown", "Nelson", "Marlborough"],
        "services": ["Consultation", "Design", "Excavation", "Construction", "Finishing"],
        "service_available": True,
        "lead_generation_title": "South Island swimming pool quotes",
        "quote_cta": "Request a South Island pool quote",
        "consultation_cta": "Book a South Island consultation",
        "href": "/service-areas/south-island",
        "phone": "0800 POOL NZ",
        "email": "quotes@example.co.nz",
    },
]

PAGES: dict[str, dict[str, Any]] = {
    "home": {
        "slug": "home",
        "title": "Nationwide Swimming Pool Installation New Zealand",
        "published": True,
        "summary": "A trusted New Zealand swimming pool company for complete pool design and installation nationwide.",
        "hero": {
            "headline": "Nationwide swimming pool installation in New Zealand",
            "subheading": "From consultation and design to excavation, construction, finishing, and handover.",
            "primary_cta": "Request a quote",
            "secondary_cta": "Book a consultation",
        },
        "sections": [
            {"heading": "Complete pool installation", "body": "We manage the full swimming pool installation process from first consultation through handover."},
            {"heading": "Project gallery", "body": "Explore completed pool projects by location, pool type, and key features."},
        ],
        "faqs": FAQS,
    },
    "services": {
        "slug": "services",
        "title": "Swimming Pool Installation Services",
        "published": True,
        "summary": "Full pool installation services including consultation, design, excavation, construction, finishing, consent guidance, and handover.",
        "installation_process": INSTALLATION_PROCESS,
        "pricing_factors": SERVICES[0]["pricing_factors"],
        "timelines": SERVICES[0]["timelines"],
        "council_consents": SERVICES[0]["council_consents"],
        "nationwide_availability": SERVICES[0]["nationwide_availability"],
        "sections": [
            {"heading": "Consultation and design", "body": "We define your goals, site conditions, pool type, and budget before preparing a practical installation plan."},
            {"heading": "Excavation and construction", "body": "Our team coordinates excavation, construction, filtration, and finishing for fibreglass and concrete pools."},
            {"heading": "Pricing factors", "body": "Pool type, size, access, ground conditions, finishes, heating, fencing, landscaping, and council consents all influence pricing."},
            {"heading": "Timelines and council consents", "body": "We explain expected timelines and council consent steps so clients understand the pathway before work begins."},
            {"heading": "Nationwide availability", "body": "We respond to swimming pool enquiries across New Zealand, including the North Island, South Island, and major regions."},
        ],
        "faqs": FAQS,
    },
    "projects": {
        "slug": "projects",
        "title": "Completed Pool Projects",
        "published": True,
        "summary": "A gallery of completed swimming pool projects with images, locations, pool types, and key features.",
        "projects": PROJECTS,
        "faqs": FAQS,
    },
    "service-areas": {
        "slug": "service-areas",
        "title": "Swimming Pool Installation Service Areas",
        "published": True,
        "summary": "Nationwide New Zealand pool installation coverage across the North Island, South Island, and major regions.",
        "service_areas": SERVICE_AREAS,
        "faqs": FAQS,
    },
    "draft-pool-page": {
        "slug": "draft-pool-page",
        "title": "Draft Pool Page",
        "published": False,
        "summary": "Unpublished content should not be returned by the public API.",
    },
}


def clone(value: Any) -> Any:
    return deepcopy(value)


def get_page(slug: str) -> dict[str, Any] | None:
    key = normalise_slug(slug) or "home"
    page = PAGES.get(key)
    if not page or not page.get("published", False):
        return None
    return clone(page)


def list_services() -> list[dict[str, Any]]:
    return clone(SERVICES)


def get_service(slug: str) -> dict[str, Any] | None:
    key = normalise_slug(slug)
    for service in SERVICES:
        if normalise_slug(service["slug"]) == key:
            return clone(service)
    return None


def list_projects() -> list[dict[str, Any]]:
    return clone(PROJECTS)


def get_project(slug: str) -> dict[str, Any] | None:
    key = PROJECT_ALIASES.get(normalise_slug(slug), normalise_slug(slug))
    for project in PROJECTS:
        if normalise_slug(project["slug"]) == key:
            return clone(project)
    return None


def list_service_areas() -> list[dict[str, Any]]:
    return clone(SERVICE_AREAS)


def get_service_area(slug: str) -> dict[str, Any] | None:
    key = normalise_slug(slug)
    for area in SERVICE_AREAS:
        if normalise_slug(area["slug"]) == key:
            return clone(area)
    return None
