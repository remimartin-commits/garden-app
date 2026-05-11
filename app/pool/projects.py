from __future__ import annotations

from copy import deepcopy

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["pool", "projects"])


def _public_case_study(project: dict) -> dict:
    loc_full = str(project.get("location") or "")
    loc_short = loc_full.split(",")[0].strip() if loc_full else ""
    pool_raw = str(project.get("pool_type") or "").lower()
    if "fibreglass" in pool_raw:
        pool_type = "Fibreglass in-ground pool"
    elif "concrete" in pool_raw:
        pool_type = "Concrete in-ground pool"
    else:
        pool_type = str(project.get("pool_type") or "")

    services_pub: list[str] = []
    for svc in project.get("services") or []:
        s = str(svc)
        if "pool design" in s.lower():
            services_pub.append("Pool design")
        else:
            services_pub.append(s.replace("-", " ").strip().capitalize())

    images: list[str] = []
    for img in project.get("images") or []:
        if isinstance(img, dict) and img.get("src"):
            images.append(str(img["src"]))
        elif isinstance(img, str):
            images.append(img)
    if not images and project.get("hero_image"):
        images.append(str(project["hero_image"]))

    return {
        "slug": project["slug"],
        "title": project["title"],
        "location": loc_short,
        "region": project.get("region", ""),
        "island": project["island"],
        "poolType": pool_type,
        "clientType": project["client_type"],
        "images": images,
        "features": list(project.get("key_features") or []),
        "services": services_pub,
        "cta": {"href": "/contact#quote"},
    }


PROJECTS = [
    {
        "slug": "auckland-family-fibreglass-pool",
        "title": "Auckland Family Fibreglass Pool Installation",
        "summary": "A low-maintenance fibreglass pool designed for a busy Auckland family wanting a safe, attractive outdoor entertaining area.",
        "location": "Auckland, North Island, New Zealand",
        "region": "Auckland",
        "island": "North Island",
        "pool_type": "Fibreglass",
        "client_type": "Homeowner",
        "status": "published",
        "hero_image": "/static/images/projects/auckland-family-fibreglass-pool.jpg",
        "images": [
            {
                "src": "/static/images/projects/auckland-family-fibreglass-pool.jpg",
                "alt": "Completed Auckland family fibreglass swimming pool installation",
            }
        ],
        "key_features": [
            "Fibreglass pool shell",
            "Family-friendly entry steps",
            "Integrated filtration and circulation equipment",
            "Pool fencing coordination",
            "Outdoor entertaining zone",
        ],
        "services": [
            "consultation",
            "pool design",
            "excavation",
            "installation",
            "filtration setup",
            "handover",
        ],
        "case_study": {
            "challenge": "The client needed a practical family pool that could be installed efficiently on a suburban Auckland site with limited access.",
            "solution": "We planned the excavation sequence, coordinated the fibreglass shell placement, installed filtration equipment, and prepared the pool for compliant fencing and handover.",
            "outcome": "The family received a durable, easy-care swimming pool with clear operating guidance and a finished outdoor area ready for summer use.",
        },
        "cta": {"label": "Request a Similar Pool Quote", "href": "/quote"},
    },
    {
        "slug": "wanaka-family-pool-retreat",
        "title": "Wanaka Family Pool Retreat",
        "summary": "A scenic South Island family pool planned around outdoor living, mountain views, and seasonal use.",
        "location": "Wanaka, Otago, South Island, New Zealand",
        "region": "Otago",
        "island": "South Island",
        "pool_type": "Concrete",
        "client_type": "Homeowner",
        "status": "published",
        "hero_image": "/static/images/projects/wanaka-family-pool-retreat.jpg",
        "images": [],
        "key_features": ["Concrete pool", "Outdoor living integration", "Heating allowance"],
        "services": ["consultation", "design", "construction", "handover"],
        "case_study": {
            "challenge": "Create a pool retreat suited to the site, climate, and family use.",
            "solution": "Developed a design-led installation plan with equipment and finishing selections matched to the location.",
            "outcome": "A comfortable family pool retreat with a clear maintenance and handover process.",
        },
        "cta": {"label": "Plan a South Island Pool", "href": "/quote"},
    },
    {
        "slug": "queenstown-luxury-concrete-pool",
        "title": "Queenstown Luxury Concrete Pool",
        "summary": "A premium concrete pool designed for alpine climate resilience and mountain outlook integration.",
        "location": "Queenstown, Otago, South Island, New Zealand",
        "region": "Otago",
        "island": "South Island",
        "pool_type": "Concrete",
        "client_type": "Homeowner",
        "status": "published",
        "hero_image": "/static/images/projects/queenstown-luxury-concrete-pool.jpg",
        "images": [
            {
                "src": "/static/images/projects/queenstown-luxury-concrete-pool.jpg",
                "alt": "Queenstown luxury concrete swimming pool installation",
            }
        ],
        "key_features": ["Heating-ready circulation", "Wind-aware enclosure coordination"],
        "services": ["consultation", "pool design", "installation", "handover"],
        "case_study": {
            "challenge": "Delivering a refined concrete pool suited to alpine wind exposure and seasonal demand.",
            "solution": "Engineered concrete specification with staged concrete pours and heating allowances at commissioning.",
            "outcome": "A durable luxury pool ready for year-round guest expectations.",
        },
        "cta": {"label": "Discuss a Queenstown pool", "href": "/quote"},
    },
]


def list_projects() -> list[dict]:
    return [deepcopy(project) for project in PROJECTS if project.get("status") == "published"]


def get_project(slug: str) -> dict:
    normalized = slug.strip("/").lower()
    for project in PROJECTS:
        if project["slug"] == normalized and project.get("status") == "published":
            return deepcopy(project)
    raise HTTPException(status_code=404, detail="Project not found")


def get_project_by_slug(slug: str) -> dict:
    return get_project(slug)


@router.get("/api/projects")
def api_list_projects() -> dict:
    projects = list_projects()
    return {"projects": projects, "items": projects, "count": len(projects)}


@router.get("/api/projects/{slug}")
def api_get_project(slug: str) -> dict:
    raw = get_project(slug)
    flat = _public_case_study(raw)
    nested = {
        "slug": flat["slug"],
        "title": flat["title"],
        "location": flat["location"],
        "region": flat["region"],
        "island": flat["island"],
        "pool_type": raw.get("pool_type"),
        "client_type": raw.get("client_type"),
        "images": flat["images"],
        "features": flat["features"],
        "services": flat["services"],
        "cta": flat["cta"],
    }
    out: dict = {"project": nested}
    out.update(flat)
    return out


@router.get("/api/projects/{slug}/")
def api_get_project_trailing_slash(slug: str) -> dict:
    return api_get_project(slug)
