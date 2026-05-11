from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.entities import PlantListing

router = APIRouter(tags=["plant-exchange"])

_listings: dict[int, PlantListing] = {}
_next_id: int = 1

_KINDS = frozenset({"wanted", "giveaway"})
_WANTED_STATUSES = frozenset({"open", "fulfilled"})
_GIVEAWAY_STATUSES = frozenset({"available", "reserved", "given"})


class PlantListingCreate(BaseModel):
    kind: Literal["wanted", "giveaway"]
    plant_name: str = Field(..., min_length=1)
    quantity: str = ""
    notes: str = ""
    status: Optional[str] = None


class PlantListingPatch(BaseModel):
    plant_name: Optional[str] = Field(default=None, min_length=1)
    quantity: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None


def _allocate_id() -> int:
    global _next_id
    lid = _next_id
    _next_id += 1
    return lid


def _default_status(kind: str) -> str:
    return "open" if kind == "wanted" else "available"


def _validate_status(kind: str, st: str) -> str:
    lowered = st.strip().lower()
    if kind == "wanted":
        if lowered not in _WANTED_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"status for wanted must be one of: {', '.join(sorted(_WANTED_STATUSES))}",
            )
    else:
        if lowered not in _GIVEAWAY_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"status for giveaway must be one of: {', '.join(sorted(_GIVEAWAY_STATUSES))}",
            )
    return lowered


@router.get("/api/v1/plant-listings")
def list_plant_listings(
    kind: Optional[Literal["wanted", "giveaway"]] = Query(default=None),
) -> dict[str, list[PlantListing]]:
    rows = list(_listings.values())
    if kind is not None:
        rows = [r for r in rows if r.kind == kind]
    rows.sort(key=lambda r: r.id, reverse=True)
    return {"listings": rows}


@router.post("/api/v1/plant-listings", status_code=status.HTTP_201_CREATED)
def create_plant_listing(body: PlantListingCreate) -> PlantListing:
    st = (body.status or _default_status(body.kind)).strip().lower()
    st = _validate_status(body.kind, st)
    lid = _allocate_id()
    listing = PlantListing(
        id=lid,
        kind=body.kind,
        plant_name=body.plant_name.strip(),
        quantity=(body.quantity or "").strip(),
        notes=(body.notes or "").strip(),
        status=st,
    )
    _listings[lid] = listing
    return listing


@router.patch("/api/v1/plant-listings/{listing_id}")
def patch_plant_listing(listing_id: int, body: PlantListingPatch) -> PlantListing:
    listing = _listings.get(listing_id)
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plant listing not found")
    data = body.model_dump(exclude_unset=True)
    if "plant_name" in data and data["plant_name"] is not None:
        listing.plant_name = data["plant_name"].strip()
    if "quantity" in data and data["quantity"] is not None:
        listing.quantity = data["quantity"].strip()
    if "notes" in data and data["notes"] is not None:
        listing.notes = data["notes"].strip()
    if "status" in data and data["status"] is not None:
        listing.status = _validate_status(listing.kind, data["status"])
    _listings[listing_id] = listing
    return listing


@router.delete("/api/v1/plant-listings/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plant_listing(listing_id: int) -> None:
    if listing_id not in _listings:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plant listing not found")
    del _listings[listing_id]
