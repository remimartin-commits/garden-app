from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, model_validator

from app.entities import Quote

router = APIRouter(tags=["quotes"])

_quotes: dict[int, Quote] = {}
_next_quote_id: int = 1

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
    quote: QuoteInput


class QuoteCreateResponse(BaseModel):
    quote: Quote


class QuoteGetResponse(BaseModel):
    quote: Quote


def _allocate_quote_id() -> int:
    global _next_quote_id
    qid = _next_quote_id
    _next_quote_id += 1
    return qid


@router.post(
    "/api/v1/quotes",
    response_model=QuoteCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_quote(body: QuoteCreateRequest) -> QuoteCreateResponse:
    """Create a GST-aware quote (NZ 15% GST); optional line_items and discount_ex_gst."""
    try:
        qi = body.quote
        qid = _allocate_quote_id()
        quote = Quote(
            quote_id=qid,
            customer_id=qi.customer_id,
            property_id=qi.property_id,
            title=qi.title,
            subtotal_ex_gst=qi.subtotal_ex_gst,
            gst_amount=qi.gst_amount,
            total_inc_gst=qi.total_inc_gst,
            status=qi.status,
            notes=qi.notes,
            valid_until=qi.valid_until,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    _quotes[qid] = quote
    return QuoteCreateResponse(quote=quote)


@router.get("/api/v1/quotes")
def list_quotes() -> dict[str, list[Quote]]:
    return {"quotes": list(_quotes.values())}


@router.get("/api/v1/quotes/{id}", response_model=QuoteGetResponse)
def get_quote(id: int) -> QuoteGetResponse:  # noqa: A002
    quote = _quotes.get(id)
    if quote is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quote not found")
    return QuoteGetResponse(quote=quote)
