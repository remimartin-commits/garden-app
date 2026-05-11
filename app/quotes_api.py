from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.entities import Quote
from app.models import Customer as CustomerORM
from app.models import Quote as QuoteORM
from app.nz_time import NZ, nz_wall_naive_to_iso_with_offset

router = APIRouter(tags=["quotes"])

_GST_RATE = 0.15


class QuoteLineItem(BaseModel):
    """Single line for services, materials, green-waste, or labour (amounts ex-GST)."""

    kind: Literal["service", "material", "green_waste", "labour"]
    description: str = Field(..., min_length=1)
    amount_ex_gst: float = Field(..., ge=0)


class QuoteInput(BaseModel):
    customer_id: int = Field(..., ge=1)
    property_id: int = Field(..., ge=1)
    title: str = Field(..., min_length=1)
    subtotal_ex_gst: float = Field(..., ge=0)
    gst_amount: float = Field(..., ge=0)
    total_inc_gst: float = Field(..., ge=0)
    status: str = "draft"
    notes: Optional[str] = None
    valid_until: Optional[str] = None
    line_items: list[QuoteLineItem] = Field(default_factory=list)
    discount_ex_gst: float = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_gst_and_line_math(self) -> QuoteInput:
        if self.line_items:
            lines_sum = round(sum(li.amount_ex_gst for li in self.line_items), 2)
            after_discount = round(max(0.0, lines_sum - self.discount_ex_gst), 2)
            if abs(after_discount - round(self.subtotal_ex_gst, 2)) > 0.02:
                raise ValueError(
                    "subtotal_ex_gst must match line_items sum minus discount_ex_gst"
                )
            expected_gst = round(after_discount * _GST_RATE, 2)
            if abs(expected_gst - round(self.gst_amount, 2)) > 0.02:
                raise ValueError("gst_amount must be 15% of subtotal_ex_gst when line_items are supplied")
            expected_total = round(after_discount + expected_gst, 2)
            if abs(expected_total - round(self.total_inc_gst, 2)) > 0.02:
                raise ValueError("total_inc_gst must equal subtotal_ex_gst + gst_amount")
        else:
            expected = round(self.subtotal_ex_gst + self.gst_amount, 2)
            if abs(self.total_inc_gst - expected) > 0.02:
                raise ValueError("total_inc_gst must equal subtotal_ex_gst + gst_amount (within 0.02)")
            if self.discount_ex_gst > 0:
                raise ValueError("discount_ex_gst requires line_items to explain the base subtotal")
        return self


class QuoteCreateRequest(BaseModel):
    """Nested ``quote`` (full control) or flat fields for the UI / quick create."""

    model_config = ConfigDict(extra="ignore")

    quote: QuoteInput | None = None
    customer_id: int | None = Field(default=None, ge=1)
    property_id: int = Field(default=1, ge=1)
    total: float | None = Field(default=None, ge=0)
    services: str | None = None
    status: str | None = None
    title: str | None = None
    notes: str | None = None
    valid_until: str | None = None
    subtotal_ex_gst: float | None = Field(default=None, ge=0)
    gst_amount: float | None = Field(default=None, ge=0)
    total_inc_gst: float | None = Field(default=None, ge=0)
    line_items: list[QuoteLineItem] = Field(default_factory=list)
    discount_ex_gst: float = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _require_quote_or_flat(self) -> QuoteCreateRequest:
        if self.quote is not None:
            return self
        if self.customer_id is None:
            raise ValueError('Provide a nested "quote" object, or flat fields including "customer_id".')
        if self.total is not None:
            return self
        if (
            self.subtotal_ex_gst is not None
            and self.gst_amount is not None
            and self.total_inc_gst is not None
        ):
            return self
        raise ValueError(
            'Provide a nested "quote" object, or flat "customer_id" with "total", '
            'or "customer_id" with subtotal_ex_gst, gst_amount, and total_inc_gst.'
        )

    def resolved_quote_input(self) -> QuoteInput:
        if self.quote is not None:
            return self.quote
        assert self.customer_id is not None
        raw_notes = (self.notes or self.services or "").strip()
        title_f = (self.title or "").strip() or (raw_notes[:200] if raw_notes else "Quick quote") or "Quick quote"
        st = (self.status or "draft").strip().lower() or "draft"
        vu = (self.valid_until or "").strip() or None
        if self.total is not None:
            total_inc = round(float(self.total), 2)
            sub_ex = round(total_inc / (1.0 + _GST_RATE), 2)
            gst = round(max(0.0, total_inc - sub_ex), 2)
            if abs(sub_ex + gst - total_inc) > 0.02:
                gst = round(total_inc - sub_ex, 2)
            return QuoteInput(
                customer_id=int(self.customer_id),
                property_id=int(self.property_id),
                title=title_f,
                subtotal_ex_gst=sub_ex,
                gst_amount=gst,
                total_inc_gst=total_inc,
                status=st,
                notes=raw_notes or None,
                valid_until=vu,
                line_items=list(self.line_items),
                discount_ex_gst=float(self.discount_ex_gst),
            )
        sub = round(float(self.subtotal_ex_gst), 2)
        gst = round(float(self.gst_amount), 2)
        tot = round(float(self.total_inc_gst), 2)
        return QuoteInput(
            customer_id=int(self.customer_id),
            property_id=int(self.property_id),
            title=title_f,
            subtotal_ex_gst=sub,
            gst_amount=gst,
            total_inc_gst=tot,
            status=st,
            notes=raw_notes or None,
            valid_until=vu,
            line_items=list(self.line_items),
            discount_ex_gst=float(self.discount_ex_gst),
        )


class QuotePatch(BaseModel):
    model_config = ConfigDict(extra="ignore")

    customer_id: int | None = Field(default=None, ge=1)
    property_id: int | None = Field(default=None, ge=1)
    title: str | None = Field(default=None, min_length=1)
    subtotal_ex_gst: float | None = Field(default=None, ge=0)
    gst_amount: float | None = Field(default=None, ge=0)
    total_inc_gst: float | None = Field(default=None, ge=0)
    status: str | None = None
    notes: str | None = None
    valid_until: str | None = None
    line_items: list[QuoteLineItem] | None = None
    discount_ex_gst: float | None = Field(default=None, ge=0)


class QuoteCreateResponse(BaseModel):
    quote: Quote


class QuoteGetResponse(BaseModel):
    quote: Quote


def _line_items_dicts(row: QuoteORM) -> list[dict]:
    if not row.line_items_json:
        return []
    try:
        data = json.loads(row.line_items_json)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    out: list[dict] = []
    for item in data:
        if isinstance(item, dict):
            out.append(item)
    return out


def _merged_quote_input(row: QuoteORM, patch: QuotePatch) -> QuoteInput:
    cur_li = []
    for x in _line_items_dicts(row):
        try:
            cur_li.append(QuoteLineItem.model_validate(x))
        except Exception:
            continue
    d: dict[str, Any] = {
        "customer_id": row.customer_id,
        "property_id": row.property_id,
        "title": row.title or "",
        "subtotal_ex_gst": float(row.subtotal_ex_gst or 0),
        "gst_amount": float(row.gst_amount or 0),
        "total_inc_gst": float(row.total_inc_gst or 0),
        "status": row.status or "draft",
        "notes": row.notes,
        "valid_until": row.valid_until,
        "line_items": cur_li,
        "discount_ex_gst": float(row.discount_ex_gst or 0),
    }
    for k, v in patch.model_dump(exclude_unset=True).items():
        if k == "line_items" and v is not None:
            d["line_items"] = [QuoteLineItem.model_validate(x) for x in v]
        else:
            d[k] = v
    return QuoteInput.model_validate(d)


def _row_to_quote(row: QuoteORM, customer_name: str | None = None) -> Quote:
    if row.created_at:
        created = nz_wall_naive_to_iso_with_offset(row.created_at) or row.created_at.isoformat()
    else:
        created = datetime.now(NZ).replace(microsecond=0).isoformat()
    lines = _line_items_dicts(row)
    return Quote(
        quote_id=row.id,
        customer_id=row.customer_id,
        property_id=row.property_id,
        title=row.title,
        subtotal_ex_gst=float(row.subtotal_ex_gst or 0),
        gst_amount=float(row.gst_amount or 0),
        total_inc_gst=float(row.total_inc_gst or 0),
        status=row.status or "draft",
        notes=row.notes,
        valid_until=row.valid_until,
        created_at=created,
        customer_name=customer_name,
        line_items=lines,
        discount_ex_gst=float(row.discount_ex_gst or 0),
    )


def _persist_line_items_json(qi: QuoteInput) -> str | None:
    if not qi.line_items:
        return None
    return json.dumps([li.model_dump() for li in qi.line_items])


@router.post(
    "/api/v1/quotes",
    response_model=QuoteCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_quote(body: QuoteCreateRequest, db: Session = Depends(get_db)) -> QuoteCreateResponse:
    """Create a GST-aware quote (NZ 15% GST); optional line_items and discount_ex_gst."""
    try:
        qi = body.resolved_quote_input()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    if db.get(CustomerORM, qi.customer_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    row = QuoteORM(
        customer_id=qi.customer_id,
        property_id=qi.property_id,
        title=qi.title,
        status=qi.status,
        subtotal_ex_gst=qi.subtotal_ex_gst,
        gst_amount=qi.gst_amount,
        total_inc_gst=qi.total_inc_gst,
        notes=qi.notes,
        valid_until=qi.valid_until,
        agreed_price=qi.total_inc_gst,
        line_items_json=_persist_line_items_json(qi),
        discount_ex_gst=qi.discount_ex_gst,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    cust = db.get(CustomerORM, row.customer_id)
    return QuoteCreateResponse(quote=_row_to_quote(row, cust.name if cust else None))


@router.patch("/api/v1/quotes/{quote_id}", response_model=QuoteGetResponse)
def patch_quote(
    quote_id: int,
    body: QuotePatch,
    db: Session = Depends(get_db),
) -> QuoteGetResponse:
    row = db.get(QuoteORM, quote_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quote not found")
    try:
        qi = _merged_quote_input(row, body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    if db.get(CustomerORM, qi.customer_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    row.customer_id = qi.customer_id
    row.property_id = qi.property_id
    row.title = qi.title
    row.status = qi.status
    row.subtotal_ex_gst = qi.subtotal_ex_gst
    row.gst_amount = qi.gst_amount
    row.total_inc_gst = qi.total_inc_gst
    row.notes = qi.notes
    row.valid_until = qi.valid_until
    row.agreed_price = qi.total_inc_gst
    row.line_items_json = _persist_line_items_json(qi)
    row.discount_ex_gst = qi.discount_ex_gst
    db.commit()
    db.refresh(row)
    cust = db.get(CustomerORM, row.customer_id)
    return QuoteGetResponse(quote=_row_to_quote(row, cust.name if cust else None))


@router.get("/api/v1/quotes")
def list_quotes(db: Session = Depends(get_db)) -> dict[str, list[Quote]]:
    rows = db.scalars(select(QuoteORM).order_by(QuoteORM.id)).all()
    cust_ids = {r.customer_id for r in rows}
    names: dict[int, str] = {}
    if cust_ids:
        for c in db.scalars(select(CustomerORM).where(CustomerORM.id.in_(cust_ids))).all():
            names[c.id] = c.name or ""
    return {"quotes": [_row_to_quote(r, names.get(r.customer_id)) for r in rows]}


@router.get("/api/v1/quotes/{id}", response_model=QuoteGetResponse)
def get_quote(id: int, db: Session = Depends(get_db)) -> QuoteGetResponse:  # noqa: A002
    row = db.get(QuoteORM, id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quote not found")
    cust = db.get(CustomerORM, row.customer_id)
    return QuoteGetResponse(quote=_row_to_quote(row, cust.name if cust else None))


@router.delete("/api/v1/quotes/{quote_id}")
def delete_quote(
    quote_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = db.get(QuoteORM, quote_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quote not found")
    db.delete(row)
    db.commit()
    return {"status": "deleted", "quote_id": quote_id}
