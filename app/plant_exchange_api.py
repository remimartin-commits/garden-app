from __future__ import annotations

from typing import Any, Literal, Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field

from app import config
from app.attachment_utils import coerce_attachments_list
from app.entities import PlantListing
from app.s3_uploads import (
    delete_all_stored_attachments_in_list,
    delete_attachments_removed_from_lists,
    enrich_attachments_for_display,
)

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
    attachments: Optional[list[Any]] = None


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


def _listing_public(listing: PlantListing) -> dict[str, Any]:
    return {
        "id": listing.id,
        "kind": listing.kind,
        "plant_name": listing.plant_name,
        "quantity": listing.quantity,
        "notes": listing.notes,
        "status": listing.status,
        "attachments": enrich_attachments_for_display(coerce_attachments_list(listing.attachments)),
    }


@router.get("/api/v1/plant-listings")
def list_plant_listings(
    kind: Optional[Literal["wanted", "giveaway"]] = Query(default=None),
) -> dict[str, list[dict[str, Any]]]:
    rows = list(_listings.values())
    if kind is not None:
        rows = [r for r in rows if r.kind == kind]
    rows.sort(key=lambda r: r.id, reverse=True)
    return {"listings": [_listing_public(x) for x in rows]}


@router.get("/api/v1/plant-listings/{listing_id}")
def get_plant_listing(listing_id: int) -> dict[str, Any]:
    listing = _listings.get(listing_id)
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plant listing not found")
    return _listing_public(listing)


@router.post("/api/v1/plant-listings", status_code=status.HTTP_201_CREATED)
def create_plant_listing(body: PlantListingCreate) -> dict[str, Any]:
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
        attachments=[],
    )
    _listings[lid] = listing
    return _listing_public(listing)


@router.patch("/api/v1/plant-listings/{listing_id}")
def patch_plant_listing(listing_id: int, body: PlantListingPatch) -> dict[str, Any]:
    listing = _listings.get(listing_id)
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plant listing not found")
    before_attachments = coerce_attachments_list(list(listing.attachments or []))
    data = body.model_dump(exclude_unset=True)
    if "plant_name" in data and data["plant_name"] is not None:
        listing.plant_name = data["plant_name"].strip()
    if "quantity" in data and data["quantity"] is not None:
        listing.quantity = data["quantity"].strip()
    if "notes" in data and data["notes"] is not None:
        listing.notes = data["notes"].strip()
    if "status" in data and data["status"] is not None:
        listing.status = _validate_status(listing.kind, data["status"])
    if "attachments" in data and data["attachments"] is not None:
        listing.attachments = coerce_attachments_list(data["attachments"])
    _listings[listing_id] = listing
    if "attachments" in data and data["attachments"] is not None:
        delete_attachments_removed_from_lists(before_attachments, listing.attachments)
    return _listing_public(listing)


@router.post("/api/v1/plant-listings/{listing_id}/attachments")
async def post_plant_listing_attachment(
    listing_id: int,
    file: UploadFile = File(...),
) -> dict[str, str]:
    if not config.s3_job_attachments_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Photo storage is not configured. Set S3_ENDPOINT_URL, S3_ACCESS_KEY_ID, "
            "S3_SECRET_ACCESS_KEY, S3_BUCKET_NAME, and S3_PUBLIC_BASE_URL.",
        )
    listing = _listings.get(listing_id)
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plant listing not found")
    body = await file.read()
    try:
        from app.s3_uploads import upload_job_image

        item = upload_job_image(
            scope="plant",
            scope_id=listing_id,
            original_filename=file.filename or "photo.jpg",
            content_type=file.content_type,
            body=body,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e
    atts = coerce_attachments_list(listing.attachments)
    atts.append(item)
    listing.attachments = atts
    _listings[listing_id] = listing
    disp = enrich_attachments_for_display([item])
    return disp[0] if disp else item


@router.delete("/api/v1/plant-listings/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plant_listing(listing_id: int) -> None:
    if listing_id not in _listings:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plant listing not found")
    listing = _listings[listing_id]
    delete_all_stored_attachments_in_list(coerce_attachments_list(listing.attachments))
    del _listings[listing_id]
