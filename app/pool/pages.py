"""Pool-only published marketing page content API.

Swimming pool installation website pages (static, cacheable).
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from fastapi import APIRouter, HTTPException, Response

router = APIRouter(prefix="/api/pages", tags=["pool", "page-content"])

CACHE_CONTROL = "public, max-age=300, stale-while-revalidate=86400"

PUBLISHED_PAGES: dict[str, dict[str, Any]] = {
    "home": {
        "slug": "home",
        "status": "published",
        "title": "Nationwide Swimming Pool Design & Installation in New Zealand",
        "description": "Complete swimming pool design and installation services for homeowners, developers, and commercial clients across New Zealand.",
        "hero": {
            "eyebrow": "Nationwide swimming pool specialists",
            "headline": "Custom pool design, construction, and handover anywhere in New Zealand",
            "heading": "Custom pool design, construction, and handover anywhere in New Zealand",
            "body": "From first consultation through excavation, construction, finishing, compliance, and handover, our team delivers reliable end-to-end swimming pool installation nationwide.",
            "primary_cta": "Request a quote",
            "secondary_cta": "View completed projects",
        },
        "sections": [
            {
                "id": "nationwide-service",
                "title": "Pool installation coverage across New Zealand",
                "body": "We support projects throughout the North Island, South Island, and major New Zealand regions with experienced design, project coordination, and installation teams.",
            },
            {
                "id": "trust",
                "title": "Trusted nationwide installers",
                "body": "Experienced teams coordinate consent guidance, excavation, construction, equipment commissioning, and handover documentation.",
            },
            {
                "id": "complete-installation",
                "title": "Complete design and build service",
                "body": "Our process covers consultation, concept design, site planning, excavation, pool construction, filtration, surrounds, finishing, and customer handover.",
            },
            {
                "id": "quote-enquiries",
                "title": "Request a tailored pool quote",
                "body": "Homeowners, builders, developers, and commercial clients can submit project details to receive a practical consultation and installation estimate.",
            },
        ],
        "seo": {
            "title": "Nationwide Swimming Pool Design & Installation in New Zealand",
            "description": "Trusted nationwide swimming pool design and installation services for residential and commercial projects throughout New Zealand.",
        },
    },
    "services": {
        "slug": "services",
        "status": "published",
        "title": "Swimming Pool Installation Services",
        "description": "Full-service swimming pool consultation, design, excavation, construction, finishing, and handover for New Zealand projects.",
        "hero": {
            "eyebrow": "Complete pool installation service",
            "headline": "Everything needed to take your pool from idea to finished handover",
            "body": "Our installation team coordinates each stage of the project so clients have one clear workflow from initial brief to completed swimming pool.",
            "primary_cta": "Plan my pool project",
            "secondary_cta": "Explore the process",
        },
        "sections": [
            {
                "id": "service-overview",
                "title": "End-to-end swimming pool delivery",
                "body": "We help with site assessment, pool type selection, design options, construction planning, installation delivery, and final commissioning.",
            },
            {
                "id": "installation-process",
                "title": "Our swimming pool installation process",
                "body": "The process starts with consultation and design, then moves through site checks, excavation, construction, plumbing and filtration, coping and surrounds, finishing, quality checks, and final handover.",
                "steps": [
                    {"title": "Consultation"},
                    {"title": "Design and planning"},
                    {"title": "Excavation and construction"},
                    {"title": "Finishing"},
                    {"title": "Handover"},
                ],
            },
            {
                "id": "client-types",
                "title": "Residential, development, and commercial projects",
                "body": "We work with homeowners, architects, developers, accommodation providers, schools, and commercial facilities needing dependable swimming pool installation support.",
            },
        ],
        "seo": {
            "title": "Swimming Pool Installation Services NZ",
            "description": "Consultation, design, excavation, construction, finishing, and handover for New Zealand swimming pool projects.",
        },
    },
    "projects": {
        "slug": "projects",
        "status": "published",
        "title": "Completed Swimming Pool Projects",
        "description": "A selection of completed pool installations showing locations, pool types, and key features.",
        "hero": {
            "eyebrow": "Project gallery",
            "headline": "Completed pools across New Zealand",
            "body": "Explore examples of family pools, architectural pools, lap pools, plunge pools, and commercial installations delivered nationwide.",
            "primary_cta": "Discuss a similar project",
            "secondary_cta": "View service areas",
        },
        "sections": [
            {
                "id": "gallery-introduction",
                "title": "Project inspiration",
                "body": "Our project gallery highlights pool locations, types, finishes, landscaping integration, and practical features to help clients plan their own installation.",
            }
        ],
        "seo": {
            "title": "Swimming Pool Project Gallery NZ",
            "description": "View completed swimming pool design and installation projects across New Zealand.",
        },
    },
    "coverage": {
        "slug": "coverage",
        "status": "published",
        "title": "Swimming Pool Installation Coverage",
        "description": "Nationwide service coverage across the North Island, South Island, and major New Zealand regions.",
        "hero": {
            "eyebrow": "Nationwide coverage",
            "headline": "Pool installation services throughout New Zealand",
            "heading": "Pool installation services throughout New Zealand",
            "body": "We support swimming pool projects in Auckland, Waikato, Bay of Plenty, Wellington, Canterbury, Otago, and other regional centres.",
            "primary_cta": "Check availability",
            "secondary_cta": "Request a quote",
        },
        "sections": [
            {
                "id": "north-island",
                "title": "North Island service areas",
                "body": "Coverage includes Auckland, Northland, Waikato, Bay of Plenty, Hawke's Bay, Taranaki, Manawatu-Whanganui, and Wellington regions.",
            },
            {
                "id": "south-island",
                "title": "South Island service areas",
                "body": "Coverage includes Nelson Tasman, Marlborough, Canterbury, West Coast, Otago, Southland, and surrounding districts.",
            },
        ],
        "seo": {
            "title": "Nationwide Swimming Pool Installation Locations NZ",
            "description": "Swimming pool design and installation coverage across New Zealand regions.",
        },
    },
    "locations": {
        "slug": "locations",
        "status": "published",
        "title": "Swimming Pool Installation Locations",
        "description": "Nationwide service coverage across the North Island, South Island, and major New Zealand regions.",
        "hero": {
            "eyebrow": "Nationwide coverage",
            "headline": "Pool installation services throughout New Zealand",
            "body": "We support swimming pool projects in Auckland, Waikato, Bay of Plenty, Wellington, Canterbury, Otago, and other regional centres.",
            "primary_cta": "Check availability",
            "secondary_cta": "Request a quote",
        },
        "sections": [
            {
                "id": "north-island",
                "title": "North Island service areas",
                "body": "Coverage includes Auckland, Northland, Waikato, Bay of Plenty, Hawke's Bay, Taranaki, Manawatu-Whanganui, and Wellington regions.",
            },
            {
                "id": "south-island",
                "title": "South Island service areas",
                "body": "Coverage includes Nelson Tasman, Marlborough, Canterbury, West Coast, Otago, Southland, and surrounding districts.",
            },
        ],
        "seo": {
            "title": "Nationwide Swimming Pool Installation Locations NZ",
            "description": "Swimming pool design and installation coverage across New Zealand regions.",
        },
    },
    "contact": {
        "slug": "contact",
        "status": "published",
        "title": "Contact Our Swimming Pool Installation Team",
        "description": "Contact the team to discuss a swimming pool design, installation, or quote enquiry.",
        "hero": {
            "eyebrow": "Start your pool project",
            "headline": "Tell us about your site, goals, timing, and budget",
            "body": "Submit an enquiry and our team will review your requirements before recommending the next step for your pool project.",
            "primary_cta": "Submit quote enquiry",
            "secondary_cta": "Call the team",
        },
        "sections": [
            {
                "id": "contact-workflow",
                "title": "What happens after you enquire",
                "body": "We review your project location, preferred pool type, site details, budget range, timing, and contact preferences before arranging a consultation.",
            }
        ],
        "seo": {
            "title": "Contact Swimming Pool Installers NZ",
            "description": "Request a consultation or quote for swimming pool design and installation in New Zealand.",
        },
    },
    "draft-pricing": {
        "slug": "draft-pricing",
        "status": "draft",
        "title": "Draft pricing page",
        "description": "Internal draft — not published.",
        "hero": {
            "eyebrow": "Draft",
            "headline": "Draft pricing",
            "heading": "Draft pricing",
            "body": "Unpublished draft content.",
            "primary_cta": "Back",
            "secondary_cta": "Contact",
        },
        "sections": [],
        "seo": {"title": "Draft", "description": "Draft"},
    },
}


def _normalise_slug(slug: str) -> str:
    """Normalise route slugs while preserving the published page contract."""
    cleaned = slug.strip().strip("/").lower()
    return cleaned or "home"


def list_pages() -> list[dict[str, Any]]:
    """Compatibility helper for app.main imports."""
    return [deepcopy(page) for page in PUBLISHED_PAGES.values() if page.get("status") == "published"]


@router.get("/{slug:path}")
def get_page(slug: str, response: Response) -> dict[str, Any]:
    """Return a published marketing page by slug."""
    response.headers["Cache-Control"] = CACHE_CONTROL
    response.headers["Vary"] = "Accept-Encoding"

    page = PUBLISHED_PAGES.get(_normalise_slug(slug))
    if not page or page.get("status") != "published":
        raise HTTPException(status_code=404, detail="Published page not found")

    return deepcopy(page)
