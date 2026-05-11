from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.entities import ServiceProperty

router = APIRouter(tags=["properties"])

_RETENTION_BLOCK_TAGS = frozenset({"retention_hold", "legal_hold"})

_properties: dict[int, ServiceProperty] = {
    1: ServiceProperty(
        id=1,
        customer_id=1,
        address="123 Garden Lane",
        access_notes="Side gate code on file",
        hazards=None,
        garden_profile="Established natives, limited access on west side",
        coastal_exposure=False,
        slope="gentle",
        pets="None on site",
        parking="Driveway, two vehicles",
        service_history=["Initial site assessment"],
        tags=[],
        archived=False,
    ),
    2: ServiceProperty(
        id=2,
        customer_id=1,
        address="99 Retention Row",
        access_notes=None,
        hazards=None,
        garden_profile=None,
        coastal_exposure=None,
        slope=None,
        pets=None,
        parking=None,
        service_history=[],
        tags=["retention_hold"],
        archived=False,
    ),
}


class PropertyArchiveResponse(BaseModel):
    message: str


def _retention_allows_archive(prop: ServiceProperty) -> bool:
    lowered = {t.lower() for t in prop.tags}
    return lowered.isdisjoint(_RETENTION_BLOCK_TAGS)


def _get_active_property(property_id: int) -> ServiceProperty | None:
    prop = _properties.get(property_id)
    if prop is None or prop.archived:
        return None
    return prop


@router.get("/api/v1/properties/{property_id}")
def get_property(property_id: int) -> ServiceProperty:
    prop = _get_active_property(property_id)
    if prop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    return prop


@router.delete(
    "/api/v1/properties/{property_id}",
    response_model=PropertyArchiveResponse,
    status_code=status.HTTP_200_OK,
)
def soft_delete_property(property_id: int) -> PropertyArchiveResponse:
    prop = _properties.get(property_id)
    if prop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    if prop.archived:
        return PropertyArchiveResponse(message="Property archived successfully")
    if not _retention_allows_archive(prop):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Property cannot be archived while retention rules apply",
        )
    prop.archived = True
    _properties[property_id] = prop
    return PropertyArchiveResponse(message="Property archived successfully")
