"""Domain entities for marketing website feature data.

These entities are intentionally framework-agnostic so they can be reused by
static pages, API handlers, persistence code, and tests without introducing new
runtime dependencies.

Do not prepend classes or other statements above this docstring: only the
docstring may precede ``from __future__ import annotations`` (PEP 236); otherwise
imports fail and pytest errors cascade across every test that imports this module.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from datetime import datetime
import re
from typing import Any, Mapping, Optional

@dataclass(init=False)
class BusinessProfile:
    name: str
    gst_number: str
    address: str
    contact_email: str
    phone_number: str

    def __post_init__(self):
        if not self.name:
            raise ValueError('Name is required')
        if not self.contact_email:
            raise ValueError('Contact email is required')
@dataclass
class JobPreview:
    job_id: int
    name: str
    description: str = ''
    is_recurring: bool = False

    def __post_init__(self):
        if not self.name:
            raise ValueError('Name is required')

@dataclass
class Role:
    name: str
    permissions: list[str]

@dataclass
class User:
    username: str
    role: Role

from pydantic import BaseModel, Field

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True, slots=True)
class Service:
    """A swimming pool installation service offered nationwide.

    Required fields model the information needed to present a service on the
    public website and qualify quote enquiries from residential or commercial
    customers.
    """

    id: str
    name: str
    slug: str
    short_description: str
    description: str
    pool_types: tuple[str, ...]
    customer_segments: tuple[str, ...]
    process_steps: tuple[str, ...]
    included_features: tuple[str, ...]
    regions_available: tuple[str, ...]
    starting_price_note: str
    duration_estimate: str
    hero_image_alt: str
    display_order: int
    is_featured: bool

    def __post_init__(self) -> None:
        self._require_text("id", self.id)
        self._require_text("name", self.name)
        self._require_text("slug", self.slug)
        self._require_text("short_description", self.short_description)
        self._require_text("description", self.description)
        self._require_text("starting_price_note", self.starting_price_note)
        self._require_text("duration_estimate", self.duration_estimate)
        self._require_text("hero_image_alt", self.hero_image_alt)

        if not _SLUG_RE.fullmatch(self.slug):
            raise ValueError("slug must be lowercase kebab-case using letters, numbers, and hyphens")

        self._require_text_sequence("pool_types", self.pool_types)
        self._require_text_sequence("customer_segments", self.customer_segments)
        self._require_text_sequence("process_steps", self.process_steps)
        self._require_text_sequence("included_features", self.included_features)
        self._require_text_sequence("regions_available", self.regions_available)

        if not isinstance(self.display_order, int):
            raise TypeError("display_order must be an integer")
        if self.display_order < 0:
            raise ValueError("display_order must be zero or greater")

        if not isinstance(self.is_featured, bool):
            raise TypeError("is_featured must be a boolean")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Service":
        """Create a Service from mapping data, coercing list fields to tuples."""

        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            slug=str(data["slug"]),
            short_description=str(data["short_description"]),
            description=str(data["description"]),
            pool_types=tuple(data["pool_types"]),
            customer_segments=tuple(data["customer_segments"]),
            process_steps=tuple(data["process_steps"]),
            included_features=tuple(data["included_features"]),
            regions_available=tuple(data["regions_available"]),
            starting_price_note=str(data["starting_price_note"]),
            duration_estimate=str(data["duration_estimate"]),
            hero_image_alt=str(data["hero_image_alt"]),
            display_order=int(data["display_order"]),
            is_featured=bool(data["is_featured"]),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dictionary representation."""

        payload = asdict(self)
        for field_name in (
            "pool_types",
            "customer_segments",
            "process_steps",
            "included_features",
            "regions_available",
        ):
            payload[field_name] = list(payload[field_name])
        return payload

    @staticmethod
    def _require_text(field_name: str, value: Any) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} is required and must be non-empty text")

    @classmethod
    def _require_text_sequence(cls, field_name: str, value: Any) -> None:
        if not isinstance(value, tuple) or not value:
            raise ValueError(f"{field_name} is required and must be a non-empty tuple")
        for item in value:
            cls._require_text(field_name, item)


@dataclass(frozen=True, slots=True)
class AuthSession:
    user_id: str
    session_id: str
    created_at: datetime
    expires_at: datetime

    def to_dict(self) -> dict:
        return {
            'session_id': self.session_id,
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat()
        }

@dataclass
class MaterialLineItem:
    """Billable material row: quantity * unit price."""

    material_id: int
    quantity: float
    unit_price: float
    description: str = ""
    name: str = ""
    gst_inclusive: bool = True

    def __post_init__(self) -> None:
        if not (str(self.description).strip() or str(self.name).strip()):
            raise ValueError("name or description is required")
        if float(self.quantity) <= 0:
            raise AssertionError("Quantity must be greater than zero")
        if float(self.unit_price) < 0:
            raise AssertionError("Unit price cannot be negative")

    @property
    def total_price(self) -> float:
        return float(self.quantity) * float(self.unit_price)


@dataclass
class JobStatusDefinition:
    name: str
    description: str
    is_active: bool = True
    system_status_category: str = ""
    quote_state: str = ""
    invoice_state: str = ""

    def __post_init__(self) -> None:
        if not self.name or not self.description:
            raise ValueError("Name and description are required")


from dataclasses import dataclass, field as _service_area_dataclass, field as _service_area_field
from typing import Any as _service_area_Any


@dataclass
class ServiceArea:
    """Represents an installation coverage area for nationwide pool projects.

    This entity supports the lead-generation website service-area content by
    describing where complete swimming pool installation services are available
    and what support is offered for customers in that area.
    """

    name: str
    island: str
    regions: list[str]
    cities: list[str]
    installation_available: bool = True
    consent_guidance_available: bool = True
    travel_notes: str = ""
    typical_site_types: list[str] = _service_area_field(default_factory=list)
    response_time: str = ""

    def __post_init__(self) -> None:
        required_text_fields = {
            "name": self.name,
            "island": self.island,
        }
        for field_name, value in required_text_fields.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"ServiceArea.{field_name} is required")

        required_list_fields = {
            "regions": self.regions,
            "cities": self.cities,
        }
        for field_name, value in required_list_fields.items():
            if not isinstance(value, list) or not value:
                raise ValueError(f"ServiceArea.{field_name} must contain at least one item")
            if any(not isinstance(item, str) or not item.strip() for item in value):
                raise ValueError(f"ServiceArea.{field_name} must contain non-empty strings")

        if not isinstance(self.installation_available, bool):
            raise ValueError("ServiceArea.installation_available must be a boolean")
        if not isinstance(self.consent_guidance_available, bool):
            raise ValueError("ServiceArea.consent_guidance_available must be a boolean")
        if not isinstance(self.typical_site_types, list):
            raise ValueError("ServiceArea.typical_site_types must be a list")
        if any(not isinstance(item, str) or not item.strip() for item in self.typical_site_types):
            raise ValueError("ServiceArea.typical_site_types must contain non-empty strings")

    def to_dict(self) -> dict[str, _service_area_Any]:
        """Return a JSON-serializable representation of the service area."""
        return {
            "name": self.name,
            "island": self.island,
            "regions": list(self.regions),
            "cities": list(self.cities),
            "installation_available": self.installation_available,
            "consent_guidance_available": self.consent_guidance_available,
            "travel_notes": self.travel_notes,
            "typical_site_types": list(self.typical_site_types),
            "response_time": self.response_time,
        }


@dataclass
class Invoice:
    def calculate_gst(self, gst_rate: float, unit_price_ex_gst: float, quantity: int, discount_ex_gst: float) -> None:
        self.gst_amount = quantity * unit_price_ex_gst * gst_rate
        self.total_inc_gst = (quantity * unit_price_ex_gst - discount_ex_gst) + self.gst_amount
    invoice_id: int
    customer_id: int
    amount: float
    status: str
    issue_date: date
    due_date: date
    jobs: list[int] = field(default_factory=list)
    custom_items: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.amount <= 0:
            raise ValueError("Amount must be positive")
        if self.issue_date >= self.due_date:
            raise ValueError("Issue date must be before due date")

    @staticmethod
    def create(jobs: list[int], custom_items: list[dict]) -> Invoice:
        """Build a placeholder invoice for job/custom line aggregation (IDs are synthetic)."""
        today = date.today()
        due = date.fromordinal(today.toordinal() + 30)
        return Invoice(
            invoice_id=1,
            customer_id=0,
            amount=1.0,
            status="Pending",
            issue_date=today,
            due_date=due,
            jobs=list(jobs),
            custom_items=list(custom_items),
        )

@dataclass
class Payment:
    id: int
    amount: float
    date: datetime
    method: str
    status: str
    invoice_id: int | None = None

    def __post_init__(self) -> None:
        if self.amount <= 0:
            raise ValueError("Amount must be positive")
        if not isinstance(self.status, str) or not self.status.strip():
            raise ValueError("Status is required and must be non-empty")

@dataclass(frozen=True)
class WeatherSnapshot:
    temperature: float
    humidity: float
    wind_speed: float
    description: str
    timestamp: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        if not -50 <= self.temperature <= 60:
            raise ValueError("Temperature must be between -50 and 60 degrees Celsius")
        if not 0 <= self.humidity <= 100:
            raise ValueError("Humidity must be between 0 and 100%")
        if not 0 <= self.wind_speed <= 400:
            raise ValueError("Wind speed must be between 0 and 400 km/h")
        if not self.description.strip():
            raise ValueError("Description is required and cannot be empty")



from dataclasses import dataclass as _page_dataclass
import re as _page_re
from typing import Any as _PageAny

_PAGE_SLUG_PATTERN = _page_re.compile(r"^[a-z0-9]+(?:[/-][a-z0-9]+)*$")


@_page_dataclass(frozen=True)
class Page:
    """Website page entity for marketing and lead-generation content.

    Required fields cover the page identity, search/display metadata, hero
    content, structured body sections, and calls to action needed for quote and
    contact workflows.
    """

    title: str
    slug: str
    meta_description: str
    hero_heading: str
    hero_subheading: str
    sections: list[dict[str, _PageAny]]
    calls_to_action: list[dict[str, str]]

    def __post_init__(self) -> None:
        self._validate_required_text("title", self.title)
        self._validate_required_text("slug", self.slug)
        self._validate_required_text("meta_description", self.meta_description)
        self._validate_required_text("hero_heading", self.hero_heading)
        self._validate_required_text("hero_subheading", self.hero_subheading)

        if not _PAGE_SLUG_PATTERN.fullmatch(self.slug):
            raise ValueError(
                "slug must use lowercase letters, numbers, hyphens, and optional path separators"
            )

        self._validate_sections(self.sections)
        self._validate_calls_to_action(self.calls_to_action)

    @staticmethod
    def _validate_required_text(field_name: str, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} is required")

    @classmethod
    def _validate_sections(cls, sections: list[dict[str, _PageAny]]) -> None:
        if not isinstance(sections, list) or not sections:
            raise ValueError("sections is required and must contain at least one section")

        for index, section in enumerate(sections):
            if not isinstance(section, dict):
                raise ValueError(f"sections[{index}] must be an object")

            cls._validate_required_text(f"sections[{index}].heading", section.get("heading"))
            body = section.get("body", section.get("content"))
            cls._validate_required_text(f"sections[{index}].content", body)

    @classmethod
    def _validate_calls_to_action(cls, calls_to_action: list[dict[str, str]]) -> None:
        if not isinstance(calls_to_action, list) or not calls_to_action:
            raise ValueError(
                "calls_to_action is required and must contain at least one call to action"
            )

        for index, call_to_action in enumerate(calls_to_action):
            if not isinstance(call_to_action, dict):
                raise ValueError(f"calls_to_action[{index}] must be an object")

            cls._validate_required_text(
                f"calls_to_action[{index}].label", call_to_action.get("label")
            )
            cls._validate_required_text(
                f"calls_to_action[{index}].url", call_to_action.get("url")
            )

    def to_dict(self) -> dict[str, _PageAny]:
        """Return a serializable representation of the page entity."""
        return {
            "title": self.title,
            "slug": self.slug,
            "meta_description": self.meta_description,
            "hero_heading": self.hero_heading,
            "hero_subheading": self.hero_subheading,
            "sections": [dict(section) for section in self.sections],
            "calls_to_action": [dict(call_to_action) for call_to_action in self.calls_to_action],
        }

    @classmethod
    def from_dict(cls, data: dict[str, _PageAny]) -> "Page":
        """Build a Page from serialized data while enforcing required fields."""
        if not isinstance(data, dict):
            raise ValueError("page data must be an object")

        required_fields = [
            "title",
            "slug",
            "meta_description",
            "hero_heading",
            "hero_subheading",
            "sections",
            "calls_to_action",
        ]
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            raise ValueError(f"missing required page fields: {', '.join(missing_fields)}")

        return cls(
            title=data["title"],
            slug=data["slug"],
            meta_description=data["meta_description"],
            hero_heading=data["hero_heading"],
            hero_subheading=data["hero_subheading"],
            sections=data["sections"],
            calls_to_action=data["calls_to_action"],
        )


try:
    __all__
except NameError:
    __all__ = ["Page"]
else:
    if "Page" not in __all__:
        __all__ = [*__all__, "Page"]


# Nationwide Swimming Pool Installation Website - Service entity
# Focused entity implementation for service information used by marketing and lead-generation pages.
from dataclasses import asdict as _service_asdict
from dataclasses import dataclass as _service_dataclass
from dataclasses import field as _service_field
from typing import Any as _ServiceAny


@_service_dataclass(slots=True)
class Service:
    """Represents a swimming pool installation service offering.

    The website uses this entity to describe end-to-end pool services, communicate
    service benefits, support project/gallery presentation, and route visitors
    toward quote enquiries.
    """

    title: str
    slug: str
    summary: str
    description: str
    service_stages: list[str] = _service_field(default_factory=list)
    included_services: list[str] = _service_field(default_factory=list)
    pool_types: list[str] = _service_field(default_factory=list)
    ideal_for: list[str] = _service_field(default_factory=list)
    coverage_regions: list[str] = _service_field(default_factory=list)
    project_features: list[str] = _service_field(default_factory=list)
    gallery_image_urls: list[str] = _service_field(default_factory=list)
    gallery_image_alt_text: list[str] = _service_field(default_factory=list)
    quote_call_to_action: str = "Request a free pool installation quote"
    enquiry_prompt: str = "Tell us about your site, preferred pool type, location, and timeframe."
    display_order: int = 0
    is_featured: bool = False

    def to_dict(self) -> dict[str, _ServiceAny]:
        """Return a serialisable representation for templates, APIs, and tests."""
        return _service_asdict(self)


# Corrective implementation for the Nationwide Swimming Pool Installation Website
# Service entity schema step. This intentionally rebinds Service to a version that
# accepts the required `id` field while keeping serialization behavior explicit.
class Service:
    """Marketing service offered by the swimming pool installation company."""

    def __post_init__(
        self,
        id,
        name="",
        description="",
        summary="",
        category="",
        features=None,
        process_steps=None,
        deliverables=None,
        suitable_for=None,
        pool_types=None,
        coverage=None,
        call_to_action="",
        **extra,
    ):
        self.id = id
        self.name = name
        self.description = description
        self.summary = summary
        self.category = category
        self.features = list(features or [])
        self.process_steps = list(process_steps or [])
        self.deliverables = list(deliverables or [])
        self.suitable_for = list(suitable_for or [])
        self.pool_types = list(pool_types or [])
        self.coverage = list(coverage or [])
        self.call_to_action = call_to_action
        self.extra = dict(extra)

    def validate(self):
        """Return a list of validation errors for required Service fields."""
        errors = []
        if not self.id:
            errors.append("Service.id is required")
        if not self.name:
            errors.append("Service.name is required")
        if not self.description:
            errors.append("Service.description is required")
        return errors

    def to_dict(self):
        data = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "summary": self.summary,
            "category": self.category,
            "features": list(self.features),
            "process_steps": list(self.process_steps),
            "deliverables": list(self.deliverables),
            "suitable_for": list(self.suitable_for),
            "pool_types": list(self.pool_types),
            "coverage": list(self.coverage),
            "call_to_action": self.call_to_action,
        }
        data.update(self.extra)
        return data

    def as_dict(self):
        return self.to_dict()

    @classmethod
    def from_dict(cls, data):
        return cls(**dict(data))

    def __eq__(self, other):
        if not isinstance(other, Service):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __repr__(self):
        return f"Service(id={self.id!r}, name={self.name!r})"


# --- Service entity: Nationwide Swimming Pool Installation Website ---
# This focused entity supports marketing/service pages for swimming pool
# installation offerings while remaining dependency-free for tests and CLI use.
import re as _service_entity_re


def _service_entity_slugify(value):
    """Create a stable URL slug from a service name/title."""
    text = str(value or "").strip().lower()
    text = _service_entity_re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def _service_entity_clean_text(value, field_name):
    """Return a stripped string or raise a helpful validation error."""
    if value is None:
        raise ValueError(f"Service requires '{field_name}'.")
    text = str(value).strip()
    if not text:
        raise ValueError(f"Service requires a non-empty '{field_name}'.")
    return text


def _service_entity_clean_list(value, field_name):
    """Validate and normalize a required list of non-empty strings."""
    if value is None:
        raise ValueError(f"Service requires '{field_name}'.")
    if isinstance(value, str):
        raise ValueError(f"Service field '{field_name}' must be a list of strings, not a string.")
    try:
        items = [str(item).strip() for item in value if str(item).strip()]
    except TypeError as exc:
        raise ValueError(f"Service field '{field_name}' must be a list of strings.") from exc
    if not items:
        raise ValueError(f"Service requires at least one '{field_name}' item.")
    return items


class Service:
    """A service offered by the nationwide swimming pool installation company.

    Required canonical fields:
    - name: display name for the service.
    - slug: URL-safe identifier; generated from name when omitted.
    - summary: short lead-generation description.
    - description: detailed service explanation.
    - process_steps: installation workflow steps.
    - features: included deliverables/key features.

    The constructor also accepts common aliases used by content schemas:
    title -> name, short_description -> summary, stages/installation_steps ->
    process_steps, and inclusions/key_features -> features.
    """

    REQUIRED_FIELDS = ("name", "slug", "summary", "description", "process_steps", "features")

    def __init__(self, **kwargs):
        self.__post_init__(**kwargs)

    def __post_init__(
        self,
        name=None,
        slug=None,
        summary=None,
        description=None,
        process_steps=None,
        features=None,
        service_type="Swimming pool installation",
        coverage="Nationwide New Zealand",
        target_clients=None,
        call_to_action="Request a free quote",
        title=None,
        short_description=None,
        stages=None,
        installation_steps=None,
        inclusions=None,
        key_features=None,
        **extra,
    ):
        if name is None:
            name = title
        if summary is None:
            summary = short_description
        if process_steps is None:
            process_steps = stages if stages is not None else installation_steps
        if features is None:
            features = inclusions if inclusions is not None else key_features
        if slug is None and name is not None:
            slug = _service_entity_slugify(name)

        self.name = _service_entity_clean_text(name, "name")
        self.title = self.name
        self.slug = _service_entity_clean_text(slug, "slug")
        self.summary = _service_entity_clean_text(summary, "summary")
        self.short_description = self.summary
        self.description = _service_entity_clean_text(description, "description")
        self.process_steps = _service_entity_clean_list(process_steps, "process_steps")
        self.stages = list(self.process_steps)
        self.installation_steps = list(self.process_steps)
        self.features = _service_entity_clean_list(features, "features")
        self.inclusions = list(self.features)
        self.key_features = list(self.features)
        self.service_type = _service_entity_clean_text(service_type, "service_type")
        self.coverage = _service_entity_clean_text(coverage, "coverage")
        self.target_clients = _service_entity_clean_list(
            target_clients or ["Homeowners", "Developers", "Commercial clients"],
            "target_clients",
        )
        self.call_to_action = _service_entity_clean_text(call_to_action, "call_to_action")
        self.extra = dict(extra)

        for key, value in self.extra.items():
            if not hasattr(self, key):
                setattr(self, key, value)

    def to_dict(self):
        """Serialize the service for templates, APIs, or generated content."""
        data = {
            "name": self.name,
            "title": self.title,
            "slug": self.slug,
            "summary": self.summary,
            "short_description": self.short_description,
            "description": self.description,
            "process_steps": list(self.process_steps),
            "stages": list(self.stages),
            "installation_steps": list(self.installation_steps),
            "features": list(self.features),
            "inclusions": list(self.inclusions),
            "key_features": list(self.key_features),
            "service_type": self.service_type,
            "coverage": self.coverage,
            "target_clients": list(self.target_clients),
            "call_to_action": self.call_to_action,
        }
        data.update(self.extra)
        return data

    @classmethod
    def from_dict(cls, data):
        """Build a Service from a dictionary."""
        if not isinstance(data, dict):
            raise ValueError("Service.from_dict requires a dictionary.")
        return cls(**data)

    def __eq__(self, other):
        if not isinstance(other, Service):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __repr__(self):
        return f"Service(name={self.name!r}, slug={self.slug!r})"


from dataclasses import dataclass, field
from typing import Any


@dataclass
class Project:
    """Completed swimming pool installation project for portfolio galleries."""

    title: str
    location: str
    region: str
    island: str
    pool_type: str
    key_features: list[str]
    image_urls: list[str]
    description: str = ""
    client_type: str = "homeowner"
    services_delivered: list[str] = field(default_factory=list)
    completion_year: int | None = None
    status: str = "completed"

    def __post_init__(self) -> None:
        self._require_text("title", self.title)
        self._require_text("location", self.location)
        self._require_text("region", self.region)
        self._require_text("island", self.island)
        self._require_text("pool_type", self.pool_type)
        self._require_text("client_type", self.client_type)
        self._require_text("status", self.status)

        allowed_islands = {"North Island", "South Island"}
        if self.island not in allowed_islands:
            raise ValueError("island must be either 'North Island' or 'South Island'")

        self._require_text_list("key_features", self.key_features)
        self._require_text_list("image_urls", self.image_urls)

        if self.services_delivered is None:
            self.services_delivered = []
        self._validate_optional_text_list("services_delivered", self.services_delivered)

        if self.description is None:
            self.description = ""
        if not isinstance(self.description, str):
            raise ValueError("description must be a string")

        if self.completion_year is not None:
            if not isinstance(self.completion_year, int):
                raise ValueError("completion_year must be an integer")
            if self.completion_year < 1900 or self.completion_year > 2100:
                raise ValueError("completion_year must be between 1900 and 2100")

    @staticmethod
    def _require_text(field_name: str, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} is required")

    @staticmethod
    def _require_text_list(field_name: str, value: list[str]) -> None:
        if not isinstance(value, list) or not value:
            raise ValueError(f"{field_name} must contain at least one item")
        Project._validate_optional_text_list(field_name, value)

    @staticmethod
    def _validate_optional_text_list(field_name: str, value: list[str]) -> None:
        if not isinstance(value, list):
            raise ValueError(f"{field_name} must be a list")
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"{field_name} must contain non-empty strings")

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "location": self.location,
            "region": self.region,
            "island": self.island,
            "pool_type": self.pool_type,
            "key_features": list(self.key_features),
            "image_urls": list(self.image_urls),
            "description": self.description,
            "client_type": self.client_type,
            "services_delivered": list(self.services_delivered),
            "completion_year": self.completion_year,
            "status": self.status,
        }


class ServiceArea:
    """Represents a geographic service coverage area for pool installations.

    Service areas are used by the marketing site to describe where the company
    provides complete swimming pool design and installation services across New
    Zealand, including island-level and regional coverage details.
    """

    REQUIRED_FIELDS = ("name", "slug", "island", "regions", "description")
    VALID_ISLANDS = {"North Island", "South Island", "Nationwide"}

    def __init__(
        self,
        name,
        slug,
        island,
        regions,
        description,
        key_locations=None,
        coverage_notes="",
        services_available=None,
        response_time="",
        active=True,
        **extra,
    ):
        self.name = self._require_text("name", name)
        self.slug = self._require_text("slug", slug)
        self.island = self._require_text("island", island)
        self.regions = self._require_text_list("regions", regions)
        self.description = self._require_text("description", description)
        self.key_locations = self._optional_text_list(key_locations)
        self.coverage_notes = coverage_notes or ""
        self.services_available = self._optional_text_list(services_available)
        self.response_time = response_time or ""
        self.active = bool(active)

        if self.island not in self.VALID_ISLANDS:
            raise ValueError(
                "island must be one of: " + ", ".join(sorted(self.VALID_ISLANDS))
            )

        for key, value in extra.items():
            setattr(self, key, value)

    @staticmethod
    def _require_text(field_name, value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} is required")
        return value.strip()

    @classmethod
    def _require_text_list(cls, field_name, value):
        values = cls._optional_text_list(value)
        if not values:
            raise ValueError(f"{field_name} must contain at least one item")
        return values

    @staticmethod
    def _optional_text_list(value):
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, (list, tuple, set)):
            raise ValueError("list field values must be a string or iterable of strings")
        cleaned = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("list field values must contain non-empty strings")
            cleaned.append(item.strip())
        return cleaned

    def to_dict(self):
        return {
            "name": self.name,
            "slug": self.slug,
            "island": self.island,
            "regions": list(self.regions),
            "description": self.description,
            "key_locations": list(self.key_locations),
            "coverage_notes": self.coverage_notes,
            "services_available": list(self.services_available),
            "response_time": self.response_time,
            "active": self.active,
        }

    def model_dump(self):
        """Compatibility helper for callers that expect Pydantic-like models."""
        return self.to_dict()

    def __repr__(self):
        return f"ServiceArea(name={self.name!r}, island={self.island!r}, regions={self.regions!r})"


try:
    __all__.append("ServiceArea")
except NameError:
    __all__ = ["ServiceArea"]
except AttributeError:
    __all__ = list(__all__) + ["ServiceArea"]


# Quote enquiry entity for nationwide swimming pool installation lead capture.
from dataclasses import dataclass, field
from datetime import datetime, timezone
import re
from typing import ClassVar, Any


_QUOTE_ENQUIRY_EMAIL_RE = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')


@dataclass(slots=True)
class QuoteEnquiry:
    """Qualified quote enquiry submitted by a prospective swimming pool client."""

    name: str
    email: str
    phone: str
    location: str
    client_type: str
    pool_type: str
    message: str
    budget_range: str | None = None
    timeframe: str | None = None
    site_address: str | None = None
    preferred_contact_method: str = 'email'
    id: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    REQUIRED_FIELDS: ClassVar[tuple[str, ...]] = (
        'name',
        'email',
        'phone',
        'location',
        'client_type',
        'pool_type',
        'message',
    )
    ALLOWED_CLIENT_TYPES: ClassVar[set[str]] = {'homeowner', 'developer', 'commercial', 'other'}
    ALLOWED_CONTACT_METHODS: ClassVar[set[str]] = {'email', 'phone'}

    def __post_init__(self) -> None:
        for field_name in (
            'name',
            'email',
            'phone',
            'location',
            'client_type',
            'pool_type',
            'message',
            'budget_range',
            'timeframe',
            'site_address',
            'preferred_contact_method',
            'id',
            'created_at',
        ):
            value = getattr(self, field_name)
            if isinstance(value, str):
                setattr(self, field_name, value.strip())

        self.email = self.email.lower()
        self.client_type = self.client_type.lower().replace(' ', '_')
        self.preferred_contact_method = self.preferred_contact_method.lower()

        errors = self.validation_errors()
        if errors:
            raise ValueError('; '.join(errors))

    @staticmethod
    def _blank(value: Any) -> bool:
        return value is None or (isinstance(value, str) and not value.strip())

    def validation_errors(self) -> list[str]:
        errors: list[str] = []

        for field_name in self.REQUIRED_FIELDS:
            if self._blank(getattr(self, field_name)):
                errors.append(f'{field_name} is required')

        if not self._blank(self.email) and not _QUOTE_ENQUIRY_EMAIL_RE.match(self.email):
            errors.append('email must be a valid email address')

        if not self._blank(self.client_type) and self.client_type not in self.ALLOWED_CLIENT_TYPES:
            allowed = ', '.join(sorted(self.ALLOWED_CLIENT_TYPES))
            errors.append(f'client_type must be one of: {allowed}')

        if not self._blank(self.preferred_contact_method) and self.preferred_contact_method not in self.ALLOWED_CONTACT_METHODS:
            allowed = ', '.join(sorted(self.ALLOWED_CONTACT_METHODS))
            errors.append(f'preferred_contact_method must be one of: {allowed}')

        return errors

    def is_valid(self) -> bool:
        return not self.validation_errors()

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'location': self.location,
            'client_type': self.client_type,
            'pool_type': self.pool_type,
            'message': self.message,
            'budget_range': self.budget_range,
            'timeframe': self.timeframe,
            'site_address': self.site_address,
            'preferred_contact_method': self.preferred_contact_method,
            'created_at': self.created_at,
        }


# Nationwide Swimming Pool Installation Website: Testimonial entity
# Kept self-contained to avoid changing existing entity behavior.
from dataclasses import asdict as _testimonial_asdict, dataclass as _testimonial_dataclass
from typing import Optional as _TestimonialOptional


@_testimonial_dataclass
class _TestimonialModel:
    """Customer testimonial for pool installation marketing pages.

    Required fields capture the customer voice, where the work was completed,
    and the type of pool project being endorsed.
    """

    customer_name: str
    location: str
    quote: str
    project_type: str
    rating: int
    pool_type: _TestimonialOptional[str] = None
    customer_role: _TestimonialOptional[str] = None
    image_url: _TestimonialOptional[str] = None

    def __post_init__(self) -> None:
        required_text_fields = {
            "customer_name": self.customer_name,
            "location": self.location,
            "quote": self.quote,
            "project_type": self.project_type,
        }
        for field_name, value in required_text_fields.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} is required")

        if not isinstance(self.rating, int):
            raise ValueError("rating must be an integer")
        if self.rating < 1 or self.rating > 5:
            raise ValueError("rating must be between 1 and 5")

    def to_dict(self) -> dict:
        """Return a JSON-serialisable representation of the testimonial."""
        return _testimonial_asdict(self)


Testimonial = _TestimonialModel


# FAQ entity for the Nationwide Swimming Pool Installation Website feature.
# Kept self-contained so it does not alter existing entity behavior.
from dataclasses import dataclass as _faq_dataclass, field as _faq_field
from typing import Any as _FAQAny


FAQ_REQUIRED_FIELDS = (
    "faq_id",
    "question",
    "answer",
    "category",
    "audience",
    "display_order",
)


FAQ_FIELD_DESCRIPTIONS = {
    "faq_id": "Stable unique identifier for the FAQ entry.",
    "question": "Customer-facing question, such as installation timing, nationwide coverage, or quote requirements.",
    "answer": "Clear marketing answer suitable for homeowners, developers, or commercial clients.",
    "category": "FAQ grouping, for example Pricing, Installation Process, Coverage, Design, or Maintenance.",
    "audience": "Primary audience for the answer, such as homeowners, developers, commercial clients, or all customers.",
    "display_order": "Positive integer used to order FAQs on the website.",
    "related_services": "Installation services referenced by the FAQ.",
    "applies_to_regions": "New Zealand regions or island coverage this FAQ applies to.",
    "is_featured": "Whether the FAQ should be highlighted in lead-generation sections.",
}


@_faq_dataclass(frozen=True)
class FAQ:
    """Frequently asked question entity for the pool installation website.

    The required fields support lead-generation content by making every FAQ
    traceable, categorized, audience-aware, and displayable in a predictable
    order across nationwide service pages.
    """

    faq_id: str
    question: str
    answer: str
    category: str
    audience: str
    display_order: int
    related_services: tuple[str, ...] = _faq_field(default_factory=tuple)
    applies_to_regions: tuple[str, ...] = _faq_field(default_factory=lambda: ("Nationwide New Zealand",))
    is_featured: bool = False

    def __post_init__(self) -> None:
        normalised_services = self._normalise_text_tuple("related_services", self.related_services)
        normalised_regions = self._normalise_text_tuple("applies_to_regions", self.applies_to_regions)
        object.__setattr__(self, "related_services", normalised_services)
        object.__setattr__(self, "applies_to_regions", normalised_regions)

        errors = self.validate()
        if errors:
            raise ValueError("Invalid FAQ entity: " + "; ".join(errors))

    @staticmethod
    def _normalise_text_tuple(field_name: str, value: tuple[str, ...] | list[str]) -> tuple[str, ...]:
        if value is None:
            return tuple()
        if isinstance(value, str):
            raise ValueError(f"Invalid FAQ entity: {field_name} must be a sequence of text values")
        try:
            return tuple(str(item).strip() for item in value if str(item).strip())
        except TypeError as exc:
            raise ValueError(f"Invalid FAQ entity: {field_name} must be iterable") from exc

    def validate(self) -> list[str]:
        errors: list[str] = []

        for field_name in ("faq_id", "question", "answer", "category", "audience"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{field_name} is required")

        if not isinstance(self.display_order, int) or isinstance(self.display_order, bool):
            errors.append("display_order must be an integer")
        elif self.display_order < 1:
            errors.append("display_order must be a positive integer")

        if not self.applies_to_regions:
            errors.append("applies_to_regions must include at least one New Zealand coverage area")

        return errors

    def to_dict(self) -> dict[str, _FAQAny]:
        return {
            "faq_id": self.faq_id.strip(),
            "question": self.question.strip(),
            "answer": self.answer.strip(),
            "category": self.category.strip(),
            "audience": self.audience.strip(),
            "display_order": self.display_order,
            "related_services": list(self.related_services),
            "applies_to_regions": list(self.applies_to_regions),
            "is_featured": self.is_featured,
        }


@dataclass
class JobPhoto:
    id: int
    job_id: int
    photo_url: str
    timestamp: datetime
    comments: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.photo_url, str) or not self.photo_url.strip():
            raise ValueError("Photo URL cannot be empty")


@dataclass
class BusinessProfile:
    """Garden-operations business tenant profile (charter)."""

    name: str
    gst_number: str
    address: str
    contact_email: str
    phone_number: str
    gst_rate: float = 0.15
    archived_at: datetime | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "name",
            "gst_number",
            "address",
            "contact_email",
            "phone_number",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} is required and must be non-empty text")

    def update_gst_rate(self, new_rate: float) -> None:
        self.gst_rate = new_rate

    def soft_archive(self) -> None:
        """Mark tenant profile as archived without destroying historical data."""
        if self.archived_at is None:
            self.archived_at = datetime.now()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "BusinessProfile":
        if not isinstance(data, Mapping):
            raise TypeError("BusinessProfile.from_dict requires a mapping")
        return cls(
            name=str(data["name"]),
            gst_number=str(data["gst_number"]),
            address=str(data["address"]),
            contact_email=str(data["contact_email"]),
            phone_number=str(data["phone_number"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "gst_number": self.gst_number,
            "address": self.address,
            "contact_email": self.contact_email,
            "phone_number": self.phone_number,
        }


class CustomerProfile:
    """Lightweight customer record used by legacy customer tests."""

    def __init__(self, name: str, contact: str, property_details: dict[str, Any]):
        self.name = name
        self.contact = contact
        self.property_details = property_details


@dataclass(frozen=True)
class OwnerUser:
    id: int
    username: str
    email: str
    is_active: bool


@dataclass
class Customer:
    """Sample customer payload for ``POST /api/v1/customers`` demos."""

    id: int
    name: str
    email: str
    phone: str = ""
    properties: list[Any] = field(default_factory=list)
    contact_details: str | None = None
    billing_details: str | None = None
    notes: str | None = None
    tags: list[str] = field(default_factory=list)
    archived: bool = False


@dataclass
class CustomerProperty:
    """A site linked to a customer in marketing / API demos."""

    id: int
    address: str
    customer_id: int


@dataclass(frozen=True)
class Property:
    """Job site / premises linked to an owner (tenant scope)."""

    property_id: int
    owner_id: int
    address: str

    def __post_init__(self) -> None:
        if not isinstance(self.property_id, int) or self.property_id < 1:
            raise ValueError("property_id must be a positive integer")
        if not isinstance(self.owner_id, int) or self.owner_id < 1:
            raise ValueError("owner_id must be a positive integer")
        if not isinstance(self.address, str) or not self.address.strip():
            raise ValueError("address is required and must be non-empty text")


@dataclass
class Job:
    """Scheduled work unit for a customer at a property."""

    job_id: int
    customer_id: int
    property_id: int
    description: str
    workflow_status: str
    system_status: str | None = None
    scheduled_date: str | None = None
    completion_date: str | None = None
    audit_log: list[str] = field(default_factory=list)
    version: int = field(default=0)

    def __post_init__(self) -> None:
        if self.scheduled_date is not None and isinstance(self.scheduled_date, str) and not self.scheduled_date.strip():
            raise ValueError("Scheduled date cannot be empty")


@dataclass
class JobCompletion:
    """Mobile/offline job update payload; delegates version checks to job_management."""

    client_id: str
    client_updated_at: str
    expected_version: int

    def submit_update(self) -> str:
        from app.job_management import handle_job_update

        return handle_job_update(self.client_id, self.client_updated_at, self.expected_version)


@dataclass(frozen=True)
class RecurringJobRule:
    """Rule for repeating a job on a schedule (tenant-configurable)."""

    rule_id: int
    customer_id: int
    cadence: str
    interval_days: int = 1
    paused: bool = False
    description: str = "A sample rule description"

    def __post_init__(self) -> None:
        if self.interval_days < 1:
            raise ValueError("interval_days must be at least 1")
        if not isinstance(self.cadence, str) or not self.cadence.strip():
            raise ValueError("cadence is required")


@dataclass(frozen=True)
class ChecklistItem:
    description: str
    is_completed: bool = False


@dataclass
class ServiceTemplate:
    name: str
    description: str
    base_price: float
    gst_enabled: bool
    active: bool = True
    labels: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.base_price < 0:
            raise ValueError("Base price cannot be negative")

    def calculate_gst(self) -> float:
        if not self.gst_enabled:
            return 0.0
        return round(self.base_price * 0.15, 2)


@dataclass
class ChecklistResult:
    id: int
    job_id: int
    checklist_items: list[str] = field(default_factory=list)
    completed_items: list[str] = field(default_factory=list)
    notes: str | None = None

    def add_completed_item(self, item: str) -> None:
        if item not in self.checklist_items:
            raise ValueError("Item not found in checklist")
        self.completed_items.append(item)


@dataclass
class Quote:
    """Formal price offer for services at a customer property (GST-aware)."""

    quote_id: int
    customer_id: int
    property_id: int
    title: str
    subtotal_ex_gst: float
    gst_amount: float
    total_inc_gst: float
    status: str
    notes: str | None = None
    valid_until: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if isinstance(self.title, str):
            self.title = self.title.strip()
        if isinstance(self.status, str):
            self.status = self.status.strip()
        if isinstance(self.notes, str):
            self.notes = self.notes.strip() or None
        if isinstance(self.valid_until, str):
            self.valid_until = self.valid_until.strip() or None

        for name in ("quote_id", "customer_id", "property_id"):
            v = getattr(self, name)
            if not isinstance(v, int) or isinstance(v, bool) or v < 1:
                raise ValueError(f"{name} must be a positive integer")
        if not isinstance(self.title, str) or not self.title.strip():
            raise ValueError("title is required")
        if not isinstance(self.status, str) or not self.status.strip():
            raise ValueError("status is required")
        for name in ("subtotal_ex_gst", "gst_amount", "total_inc_gst"):
            v = getattr(self, name)
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                raise TypeError(f"{name} must be a number")
            if float(v) < 0:
                raise ValueError(f"{name} must be non-negative")


@dataclass
class Attachment:
    """File metadata stored against jobs, quotes, or other records."""

    id: int
    filename: str
    file_url: str
    entity_type: str = "job"
    entity_id: int = 0
    file: Any | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, int) or isinstance(self.id, bool) or self.id < 1:
            raise ValueError("id must be a positive integer")
        if not isinstance(self.filename, str) or not self.filename.strip():
            raise ValueError("filename is required")
        if not isinstance(self.file_url, str) or not self.file_url.strip():
            raise ValueError("file_url is required")


@dataclass
class CustomizationSetting:
    """Named customization option with default and effective current value."""

    name: str
    description: str
    default_value: str = ""
    current_value: str | None = None
    owner_controlled: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Name must be provided for CustomizationSetting.")
        if self.current_value is None:
            self.current_value = self.default_value


_NOTIFICATION_LOG_ALLOWED_STATUSES = frozenset({"sent"})


@dataclass
class NotificationLog:
    """Record of a notification attempt (delivery audit trail)."""

    id: int
    message: str
    recipient: str | None = None
    created_at: datetime | None = None
    sent_at: datetime | None = None
    status: str | None = None
    read: bool = False
    related_entity_type: str | None = None
    related_entity_id: int | None = None

    def __post_init__(self) -> None:
        if self.created_at is not None and not isinstance(self.created_at, datetime):
            raise ValueError("created_at must be a datetime instance")
        if self.sent_at is not None and not isinstance(self.sent_at, datetime):
            raise ValueError("sent_at must be a datetime instance")
        if self.status is not None and self.status not in _NOTIFICATION_LOG_ALLOWED_STATUSES:
            raise ValueError(f"Invalid status: {self.status}")


@dataclass
class AuditLog:
    """Record of a domain change for compliance and traceability."""

    id: int
    action: str
    entity: str
    entity_id: int
    timestamp: datetime = field(default_factory=datetime.utcnow)
    performed_by: int | None = None
    details: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.timestamp, datetime):
            raise ValueError("timestamp must be a datetime object")


class DashboardMetrics(BaseModel):
    """Owner dashboard summary returned by GET /api/v1/dashboard."""

    jobs: list[Any] = Field(default_factory=list)
    revenue: int = 0
    overdue_invoices: list[Any] = Field(default_factory=list)
    upcoming_work: list[Any] = Field(default_factory=list)
    weather_risks: list[Any] = Field(default_factory=list)
    staff_availability: list[Any] = Field(default_factory=list)


@dataclass
class ServiceProperty:
    id: int
    customer_id: int
    address: str
    access_notes: str | None = None
    hazards: str | None = None
    garden_profile: str | None = None
    coastal_exposure: bool | None = None
    slope: str | None = None
    pets: str | None = None
    parking: str | None = None
    service_history: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    archived: bool = False

    def __post_init__(self) -> None:
        if not self.address:
            raise ValueError("Address is required")


@dataclass
class JobDetails:
    service_id: int
    property_id: int
    scheduled_date: str
    is_lead: bool = False


@dataclass
class JobCompleteRequest:
    final_notes: str
    actual_time: float  # in hours
    materials_used: list[str]
    checklist_results: dict[str, bool]
    attachments: list[str]

    def validate(self) -> None:
        if self.actual_time <= 0:
            raise ValueError("Actual time must be positive")
@dataclass
class CustomSetting:
    category: str
    key: str
    value: Any
    def update_value(self, new_value: Any) -> None:
        self.value = new_value
        # Additional logic for validation or constraints can be implemented here.


class AuditLogEntry:
    def __init__(self, entity, actor, action, timestamp):
        self.entity = entity
        self.actor = actor
        self.action = action
        self.timestamp = timestamp

    def to_dict(self):
        return {
            "entity": self.entity,
            "actor": self.actor,
            "action": self.action,
            "timestamp": self.timestamp
        }


class BusinessPerformanceReportParams:
    def __init__(self, start_date, end_date, service_type, suburb, customer_type, staff_member):
        self.start_date = start_date
        self.end_date = end_date
        self.service_type = service_type
        self.suburb = suburb
        self.customer_type = customer_type
        self.staff_member = staff_member

def get_customer_by_id_and_business_id(customer_id: int, business_id: int):
    # Implement query to fetch customer by customer_id and business_id
    pass

def get_job_by_id_and_business_id(job_id: int, business_id: int):
    # Implement query to fetch job by job_id and business_id
    pass

def get_invoice_by_id_and_business_id(invoice_id: int, business_id: int):
    # Implement query to fetch invoice by invoice_id and business_id
    pass

def get_audit_logs_by_business_id(log_id: int, business_id: int):
    # Implement query to fetch audit logs by log_id and business_id
    pass
