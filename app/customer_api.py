from __future__ import annotations

import csv
import json
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.audit_api import append_audit_log
from app.database import get_db
from app.entities import Customer, CustomerProperty
from app.models import Customer as CustomerORM

router = APIRouter(tags=["customers"])

_RETENTION_BLOCK_TAGS = frozenset({"retention_hold", "legal_hold"})
DEFAULT_FUEL_COST = 10.0


class CustomerCreateRequest(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    property_address: Optional[str] = None
    price_agreed_type: Optional[Literal["hourly", "fixed"]] = None
    price_agreed_amount: Optional[float] = None
    fuel_cost: Optional[float] = Field(default=None, ge=0)


class CustomerPatchRequest(BaseModel):
    """Partial update for contact, billing, notes, tags, primary property address, agreed pricing, or fuel cost."""

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
    fuel_cost: Optional[float] = Field(default=None, ge=0)


class ArchiveSuccessResponse(BaseModel):
    message: str


def _tags_from_column(raw: str | None) -> list[str]:
    if not raw or not str(raw).strip():
        return []
    s = str(raw).strip()
    if s.startswith("["):
        try:
            out = json.loads(s)
            return [str(x) for x in out] if isinstance(out, list) else []
        except json.JSONDecodeError:
            return []
    return [t.strip() for t in s.split(",") if t.strip()]


def _tags_to_column(tags: list[str]) -> str:
    return json.dumps(list(tags))


def _retention_allows_archive(customer: Customer) -> bool:
    lowered = {t.lower() for t in customer.tags}
    return lowered.isdisjoint(_RETENTION_BLOCK_TAGS)


def _row_to_customer(row: CustomerORM) -> Customer:
    props: list[CustomerProperty] = []
    if row.address and str(row.address).strip():
        props.append(CustomerProperty(id=1, address=str(row.address).strip(), customer_id=row.id))
    return Customer(
        id=row.id,
        name=row.name,
        email=row.email or "",
        phone=row.phone or "",
        properties=props,
        contact_details=row.contact_details,
        billing_details=row.billing_details,
        notes=row.notes,
        tags=_tags_from_column(row.tags),
        archived=bool(row.is_archived),
        price_agreed_type=row.price_agreed_type,
        price_agreed_amount=row.price_agreed_amount,
        fuel_cost=float(row.fuel_cost) if getattr(row, "fuel_cost", None) is not None else DEFAULT_FUEL_COST,
    )


def _sync_primary_property_address_entity(customer: Customer, address: str | None) -> None:
    addr = (address or "").strip()
    if customer.properties:
        customer.properties[0].address = addr
    elif addr:
        customer.properties.append(CustomerProperty(id=1, address=addr, customer_id=customer.id))


def _sync_primary_property_address_row(row: CustomerORM, address: str | None) -> None:
    addr = (address or "").strip()
    row.address = addr or None


def _create_customer_row(db: Session, request: CustomerCreateRequest) -> CustomerORM:
    ptype: str | None = None
    pamt: float | None = None
    if request.price_agreed_amount is not None:
        pamt = float(request.price_agreed_amount)
        raw_t = request.price_agreed_type or "fixed"
        ptype = raw_t if raw_t in ("hourly", "fixed") else "fixed"
    fuel = DEFAULT_FUEL_COST
    if request.fuel_cost is not None:
        fuel = float(request.fuel_cost)
    row = CustomerORM(
        name=request.name,
        email=request.email,
        phone=request.phone or "",
        address=(request.property_address or "").strip() or None,
        notes=None,
        tags=_tags_to_column([]),
        contact_details=None,
        billing_details=None,
        price_agreed_type=ptype,
        price_agreed_amount=pamt,
        fuel_cost=fuel,
        is_archived=False,
    )
    db.add(row)
    db.flush()
    return row


@router.post("/api/v1/customers")
def create_customer(request: CustomerCreateRequest, db: Session = Depends(get_db)) -> Customer:
    row = _create_customer_row(db, request)
    db.commit()
    db.refresh(row)
    return _row_to_customer(row)


@router.get("/api/v1/customers")
def list_customers(db: Session = Depends(get_db)) -> dict[str, list[Customer]]:
    """Active customers only (not archived). Use DELETE to archive / remove from UI."""
    rows = (
        db.query(CustomerORM)
        .filter(CustomerORM.is_archived.is_(False))
        .order_by(CustomerORM.id)
        .all()
    )
    return {"customers": [_row_to_customer(r) for r in rows]}


@router.get("/api/v1/customers/{customer_id}")
def get_customer(customer_id: int, db: Session = Depends(get_db)) -> Customer:
    row = db.get(CustomerORM, customer_id)
    if row is None or row.is_archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return _row_to_customer(row)


@router.patch("/api/v1/customers/{customer_id}")
def patch_customer(customer_id: int, body: CustomerPatchRequest, db: Session = Depends(get_db)) -> Customer:
    row = db.get(CustomerORM, customer_id)
    if row is None or row.is_archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    customer = _row_to_customer(row)
    raw = body.model_dump(exclude_unset=True)
    data = dict(raw)
    if "property_address" in data:
        _sync_primary_property_address_entity(customer, data.pop("property_address"))
        _sync_primary_property_address_row(row, customer.properties[0].address if customer.properties else None)

    had_amt = "price_agreed_amount" in raw
    had_typ = "price_agreed_type" in raw
    if had_amt or had_typ:
        data.pop("price_agreed_amount", None)
        data.pop("price_agreed_type", None)
        new_amt = raw["price_agreed_amount"] if had_amt else customer.price_agreed_amount
        new_typ = raw["price_agreed_type"] if had_typ else customer.price_agreed_type
        if had_amt and new_amt is None:
            row.price_agreed_amount = None
            row.price_agreed_type = None
        elif new_amt is not None:
            row.price_agreed_amount = float(new_amt)
            t = (new_typ or customer.price_agreed_type or "fixed").lower()
            row.price_agreed_type = t if t in ("hourly", "fixed") else "fixed"
        elif had_typ and new_typ is not None and customer.price_agreed_amount is not None:
            t = str(new_typ).lower()
            if t in ("hourly", "fixed"):
                row.price_agreed_type = t

    for key, value in data.items():
        if key == "tags" and value is not None:
            row.tags = _tags_to_column(list(value))
        elif value is not None:
            setattr(row, key, value)

    db.commit()
    db.refresh(row)
    return _row_to_customer(row)


@router.delete(
    "/api/v1/customers/{customer_id}",
    response_model=ArchiveSuccessResponse,
    status_code=status.HTTP_200_OK,
)
def soft_delete_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    x_actor_user_id: int = Header(default=0, alias="X-Actor-User-Id"),
) -> ArchiveSuccessResponse:
    row = db.get(CustomerORM, customer_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    customer = _row_to_customer(row)
    if row.is_archived:
        return ArchiveSuccessResponse(message="Customer archived successfully")
    if not _retention_allows_archive(customer):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Customer cannot be archived while retention rules apply",
        )
    before = {"customer_id": customer_id, "archived": row.is_archived}
    row.is_archived = True
    db.commit()
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
    db: Session = Depends(get_db),
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
        _create_customer_row(db, req)
    db.commit()
    return {"status": "success", "message": "Customers and properties imported successfully."}
