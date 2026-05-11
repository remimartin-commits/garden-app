from __future__ import annotations

import csv
from typing import Literal, Optional

from fastapi import APIRouter, File, Header, HTTPException, Query, UploadFile, status
from pydantic import BaseModel

from app.audit_api import append_audit_log
from app.entities import Customer, CustomerProperty

router = APIRouter(tags=["customers"])

_customers: dict[int, Customer] = {}
_next_customer_id: int = 1

# Tag (case-insensitive) that blocks soft-archive under retention rules.
_RETENTION_BLOCK_TAGS = frozenset({"retention_hold", "legal_hold"})


class CustomerCreateRequest(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    property_address: Optional[str] = None
    price_agreed_type: Optional[Literal["hourly", "fixed"]] = None
    price_agreed_amount: Optional[float] = None


class CustomerPatchRequest(BaseModel):
    """Partial update for contact, billing, notes, tags, primary property address, or agreed pricing."""

    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    property_address: Optional[str] = None
    contact_details: Optional[str] = None
    billing_details: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[list[str]] = None
    price_agreed_type: Optional[Literal["hourly", "fixed"]] = None
    price_agreed_amount: Optional[float] = None


class ArchiveSuccessResponse(BaseModel):
    message: str


def _retention_allows_archive(customer: Customer) -> bool:
    lowered = {t.lower() for t in customer.tags}
    return lowered.isdisjoint(_RETENTION_BLOCK_TAGS)


def _allocate_customer_id() -> int:
    global _next_customer_id
    cid = _next_customer_id
    _next_customer_id += 1
    return cid


def _get_active_customer(customer_id: int) -> Customer | None:
    customer = _customers.get(customer_id)
    if customer is None or customer.archived:
        return None
    return customer


def _sync_primary_property_address(customer: Customer, address: str | None) -> None:
    """Update or create the customer's first property row from a single address string."""
    addr = (address or "").strip()
    if customer.properties:
        customer.properties[0].address = addr
    elif addr:
        customer.properties.append(
            CustomerProperty(id=1, address=addr, customer_id=customer.id)
        )


@router.post("/api/v1/customers")
def create_customer(request: CustomerCreateRequest) -> Customer:
    cid = _allocate_customer_id()
    ptype: str | None = None
    pamt: float | None = None
    if request.price_agreed_amount is not None:
        pamt = float(request.price_agreed_amount)
        raw_t = request.price_agreed_type or "fixed"
        ptype = raw_t if raw_t in ("hourly", "fixed") else "fixed"
    customer = Customer(
        id=cid,
        name=request.name,
        email=request.email,
        phone=request.phone or "",
        price_agreed_type=ptype,
        price_agreed_amount=pamt,
    )
    if request.property_address:
        prop = CustomerProperty(id=1, address=request.property_address, customer_id=cid)
        customer.properties.append(prop)
    _customers[cid] = customer
    return customer


@router.get("/api/v1/customers")
def list_customers() -> dict[str, list[Customer]]:
    return {"customers": list(_customers.values())}


@router.get("/api/v1/customers/{customer_id}")
def get_customer(customer_id: int) -> Customer:
    customer = _get_active_customer(customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return customer


@router.patch("/api/v1/customers/{customer_id}")
def patch_customer(customer_id: int, body: CustomerPatchRequest) -> Customer:
    customer = _get_active_customer(customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    raw = body.model_dump(exclude_unset=True)
    data = dict(raw)
    if "property_address" in data:
        _sync_primary_property_address(customer, data.pop("property_address"))
    had_amt = "price_agreed_amount" in raw
    had_typ = "price_agreed_type" in raw
    if had_amt or had_typ:
        data.pop("price_agreed_amount", None)
        data.pop("price_agreed_type", None)
        new_amt = raw["price_agreed_amount"] if had_amt else customer.price_agreed_amount
        new_typ = raw["price_agreed_type"] if had_typ else customer.price_agreed_type
        if had_amt and new_amt is None:
            customer.price_agreed_amount = None
            customer.price_agreed_type = None
        elif new_amt is not None:
            customer.price_agreed_amount = float(new_amt)
            t = (new_typ or customer.price_agreed_type or "fixed").lower()
            customer.price_agreed_type = t if t in ("hourly", "fixed") else "fixed"
        elif had_typ and new_typ is not None and customer.price_agreed_amount is not None:
            t = str(new_typ).lower()
            if t in ("hourly", "fixed"):
                customer.price_agreed_type = t
    for key, value in data.items():
        if key == "tags" and value is not None:
            customer.tags = list(value)
        elif value is not None:
            setattr(customer, key, value)

    _customers[customer_id] = customer
    return customer


@router.delete(
    "/api/v1/customers/{customer_id}",
    response_model=ArchiveSuccessResponse,
    status_code=status.HTTP_200_OK,
)
def soft_delete_customer(
    customer_id: int,
    x_actor_user_id: int = Header(default=0, alias="X-Actor-User-Id"),
) -> ArchiveSuccessResponse:
    customer = _customers.get(customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    if customer.archived:
        return ArchiveSuccessResponse(message="Customer archived successfully")
    if not _retention_allows_archive(customer):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Customer cannot be archived while retention rules apply",
        )
    before = {"customer_id": customer_id, "archived": customer.archived}
    customer.archived = True
    _customers[customer_id] = customer
    append_audit_log(
        action="DELETE",
        entity="Customer",
        entity_id=customer_id,
        before=before,
        after={"customer_id": customer_id, "archived": True},
        actor_user_id=x_actor_user_id,
    )
    return ArchiveSuccessResponse(message="Customer archived successfully")


@router.post("/api/v1/imports/customers")
async def import_customers_csv(
    file: UploadFile = File(...),
    dry_run: bool = Query(default=False),
) -> dict[str, str]:
    """Import customers from a CSV (name, email, optional phone, address/property_address).

    With ``dry_run=true``, rows are validated via ``CustomerCreateRequest`` but nothing is persisted.
    """
    raw = (await file.read()).decode("utf-8")
    reader = csv.DictReader(raw.splitlines())
    pending: list[CustomerCreateRequest] = []
    for row in reader:
        name = (row.get("name") or "").strip()
        email = (row.get("email") or "").strip()
        if not name or not email:
            continue
        pending.append(
            CustomerCreateRequest(
                name=name,
                email=email,
                phone=(row.get("phone") or "").strip() or None,
                property_address=(row.get("address") or row.get("property_address") or "").strip() or None,
            )
        )
    if dry_run:
        return {"status": "success", "message": "Dry run: validation complete; no customers were created."}
    for req in pending:
        create_customer(req)
    return {"status": "success", "message": "Customers and properties imported successfully."}
