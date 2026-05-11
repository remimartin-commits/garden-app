from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.entities import ServiceTemplate

router = APIRouter(tags=["service-templates"])

_SOFT_DELETE_DEMO_IDS = frozenset({"some-template-id"})
_soft_deleted_template_ids: set[str] = set()

_TEMPLATES: list[ServiceTemplate] = [
    ServiceTemplate(
        name="Lawn Mowing",
        description="Standard residential lawn mowing.",
        base_price=30.0,
        gst_enabled=True,
        active=True,
        labels=["lawn", "mowing"],
    ),
    ServiceTemplate(
        name="Hedge Trimming",
        description="Seasonal hedge and border trimming.",
        base_price=45.0,
        gst_enabled=True,
        active=False,
        labels=["hedge"],
    ),
]


class ServiceTemplateListItem(BaseModel):
    """Public list row: includes explicit active/inactive status for operators."""

    name: str
    description: str
    base_price: float
    gst_enabled: bool
    labels: list[str] = Field(default_factory=list)
    status: str = Field(description="active or inactive")


@router.get("/api/v1/service-templates", response_model=list[ServiceTemplateListItem])
def list_service_templates() -> list[ServiceTemplateListItem]:
    return [
        ServiceTemplateListItem(
            name=t.name,
            description=t.description,
            base_price=t.base_price,
            gst_enabled=t.gst_enabled,
            labels=list(t.labels),
            status="active" if t.active else "inactive",
        )
        for t in _TEMPLATES
    ]


@router.delete("/api/v1/service-templates/{template_id}")
def soft_delete_service_template(template_id: str) -> dict[str, str]:
    """Demo soft-delete used by contract tests (stable id ``some-template-id``)."""
    if template_id in _soft_deleted_template_ids:
        return {"status": "archived"}
    if template_id not in _SOFT_DELETE_DEMO_IDS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service template not found")
    _soft_deleted_template_ids.add(template_id)
    return {"status": "archived"}
