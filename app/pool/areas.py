from __future__ import annotations

from copy import deepcopy
from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["pool", "service-areas"])

SERVICE_AREAS = [
    {
        "slug": "nationwide-new-zealand",
        "name": "Nationwide New Zealand",
        "title": "Nationwide Swimming Pool Installation Coverage",
        "summary": "Swimming pool design and installation support for homeowners, developers, and commercial clients across New Zealand.",
        "island": "North Island and South Island",
        "regions": [
            "Auckland",
            "Northland",
            "Waikato",
            "Bay of Plenty",
            "Hawke's Bay",
            "Wellington",
            "Tasman",
            "Marlborough",
            "Canterbury",
            "Otago",
            "Queenstown Lakes",
            "Southland",
        ],
        "coverage_type": "nationwide",
        "lead_generation_heading": "Request a nationwide pool installation quote",
        "lead_generation_copy": "Share your location, site details, pool type, budget range, and ideal timeframe so we can confirm availability and the best next step.",
        "cta": {"label": "Request a Quote", "href": "/quote"},
        "services_available": [
            "Consultation",
            "Pool design",
            "Council consent guidance",
            "Excavation planning",
            "Pool construction and installation",
            "Finishing, commissioning, and handover",
        ],
    },
    {
        "slug": "north-island",
        "name": "North Island",
        "title": "North Island Pool Installation Services",
        "summary": "Pool installation enquiries are supported across Auckland, Northland, Waikato, Bay of Plenty, Hawke's Bay, Wellington, and surrounding regions.",
        "island": "North Island",
        "regions": ["Auckland", "Northland", "Waikato", "Bay of Plenty", "Hawke's Bay", "Wellington"],
        "coverage_type": "regional",
        "lead_generation_heading": "Plan a North Island pool project",
        "lead_generation_copy": "Tell us about your North Island site and project goals for a qualified consultation.",
        "cta": {"label": "Book a Consultation", "href": "/quote"},
        "services_available": ["Consultation", "Design", "Excavation", "Installation", "Handover"],
    },
    {
        "slug": "south-island",
        "name": "South Island",
        "title": "South Island Pool Installation Services",
        "summary": "Pool installation enquiries are supported across Canterbury, Otago, Queenstown Lakes, Southland, Tasman, Marlborough, and nearby areas.",
        "island": "South Island",
        "regions": ["Canterbury", "Otago", "Queenstown Lakes", "Southland", "Tasman", "Marlborough"],
        "coverage_type": "regional",
        "lead_generation_heading": "Plan a South Island pool project",
        "lead_generation_copy": "Share your South Island location, access requirements, preferred pool type, and timeframe for a practical next step.",
        "cta": {"label": "Request a South Island Quote", "href": "/quote"},
        "services_available": ["Consultation", "Design", "Consent guidance", "Installation", "Handover"],
    },
]

SERVICE_AREA_CONTENT = {
    "title": "Nationwide New Zealand Swimming Pool Installation Coverage",
    "intro": "We provide swimming pool design and installation services nationwide across New Zealand, including the North Island, South Island, Auckland, Wellington, Canterbury, Otago, Waikato, Bay of Plenty, and other major regions.",
    "areas": SERVICE_AREAS,
}


def list_service_areas() -> list[dict]:
    return [deepcopy(area) for area in SERVICE_AREAS]


def get_service_area(slug: str) -> dict:
    normalized = slug.strip("/").lower()
    for area in SERVICE_AREAS:
        if area["slug"] == normalized:
            return deepcopy(area)
    raise HTTPException(status_code=404, detail="Service area not found")


@router.get("/api/service-areas")
def api_list_service_areas() -> dict:
    nz_pool_summary = (
        "Nationwide swimming pool design and installation across New Zealand regions, "
        "including consultation, excavation, construction, finishing, and handover."
    )
    regions_nested = [
        {
            "island": "North Island",
            "locations": [
                "Auckland",
                "Northland",
                "Waikato",
                "Bay of Plenty",
                "Hawke's Bay",
                "Taranaki",
                "Manawatu-Whanganui",
                "Wellington",
            ],
        },
        {
            "island": "South Island",
            "locations": [
                "Christchurch",
                "Canterbury",
                "Otago",
                "Queenstown",
                "Dunedin",
                "Southland",
                "Nelson",
                "Marlborough",
                "West Coast",
            ],
        },
    ]
    catalog = [
        ("auckland", "Auckland", "North Island", ["Auckland CBD", "North Shore", "West Auckland"]),
        ("wellington-region", "Wellington Region", "North Island", ["Wellington CBD", "Hutt Valley"]),
        ("waikato", "Waikato", "North Island", ["Hamilton", "Cambridge", "Taupo"]),
        ("bay-of-plenty", "Bay of Plenty", "North Island", ["Tauranga", "Rotorua"]),
        ("hawkes-bay", "Hawke's Bay", "North Island", ["Napier", "Hastings"]),
        ("northland", "Northland", "North Island", ["Whangarei", "Kerikeri"]),
        ("canterbury", "Canterbury", "South Island", ["Christchurch", "Timaru", "Ashburton"]),
        ("otago", "Otago", "South Island", ["Dunedin", "Queenstown", "Wanaka"]),
        ("nelson-tasman", "Nelson Tasman", "South Island", ["Nelson", "Richmond"]),
        ("southland", "Southland", "South Island", ["Invercargill", "Gore"]),
    ]
    service_areas = [
        {
            "slug": slug,
            "name": name,
            "island": island,
            "available": True,
            "summary": f"Swimming pool installation and consultation coverage for {name}, including residential pool projects.",
            "key_locations": locs,
        }
        for slug, name, island, locs in catalog
    ]

    return {
        "headline": SERVICE_AREA_CONTENT["title"],
        "summary": SERVICE_AREA_CONTENT["intro"],
        "service_note": nz_pool_summary,
        "regions": regions_nested,
        "coverage": {
            "country": "New Zealand",
            "nationwide": True,
            "islands": ["North Island", "South Island"],
        },
        "service_areas": service_areas,
        "items": service_areas,
        "count": len(service_areas),
    }


@router.get("/api/service-areas/{slug}")
def api_get_service_area(slug: str) -> dict:
    area = get_service_area(slug)
    return {"service_area": area}
