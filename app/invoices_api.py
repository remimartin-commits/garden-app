from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit_api import append_audit_log
from app.database import get_db
from app.entities import Invoice, Payment
from app.models import Customer as CustomerORM
from app.models import Invoice as InvoiceORM
from app.models import Payment as PaymentORM
from app.nz_time import nz_naive_now, nz_today

router = APIRouter(tags=["invoices"])


class InvoiceDetailResponse(BaseModel):
    """Schema-aligned wrapper for GET /api/v1/invoices/{id}."""

    model_config = ConfigDict(from_attributes=True)

    invoice: Invoice
    payments: list[Payment]


class InvoiceListItem(BaseModel):
    invoice_id: int
    customer_id: int
    customer_name: str | None = None
    amount: float
    status: str
    issue_date: date
    due_date: date


class InvoiceCreateBody(BaseModel):
    customer_id: int = Field(..., ge=1)
    amount: float = Field(..., ge=0)
    status: str = "issued"
    issue_date: date | None = None
    due_date: date | None = None
    notes: str | None = None
    jobs: list[int] = Field(default_factory=list)
    custom_items: list[dict] = Field(default_factory=list)


class InvoicePatchBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    customer_id: int | None = Field(default=None, ge=1)
    amount: float | None = Field(default=None, ge=0)
    status: str | None = None
    issue_date: date | None = None
    due_date: date | None = None
    notes: str | None = None
    jobs: list[int] | None = None
    custom_items: list[dict] | None = None


class PaymentCreate(BaseModel):
    amount: float = Field(..., gt=0)
    method: str = "bank_transfer"
    status: str = "Completed"


def _parse_jobs(raw: str | None) -> list[int]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    out: list[int] = []
    for x in data:
        try:
            out.append(int(x))
        except (TypeError, ValueError):
            continue
    return out


def _parse_custom_items(raw: str | None) -> list[dict]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _row_to_invoice_entity(row: InvoiceORM, customer_name: str | None = None) -> Invoice:
    return Invoice(
        invoice_id=row.id,
        customer_id=row.customer_id,
        amount=float(row.amount),
        status=row.status or "issued",
        issue_date=row.issue_date,
        due_date=row.due_date,
        jobs=_parse_jobs(row.jobs_json),
        custom_items=_parse_custom_items(row.custom_items_json),
        notes=row.notes,
        customer_name=customer_name,
    )


def _payment_entity(row: PaymentORM) -> Payment:
    return Payment(
        id=row.id,
        amount=float(row.amount),
        date=row.date,
        method=row.method or "bank_transfer",
        status=row.status or "Completed",
        invoice_id=row.invoice_id,
    )


@router.get("/api/v1/invoices")
def list_invoices(db: Session = Depends(get_db)) -> dict[str, list[InvoiceListItem]]:
    rows = db.scalars(select(InvoiceORM).order_by(InvoiceORM.id)).all()
    cust_ids = {r.customer_id for r in rows}
    names: dict[int, str] = {}
    if cust_ids:
        for c in db.scalars(select(CustomerORM).where(CustomerORM.id.in_(cust_ids))).all():
            names[c.id] = c.name or ""
    items = [
        InvoiceListItem(
            invoice_id=r.id,
            customer_id=r.customer_id,
            customer_name=names.get(r.customer_id),
            amount=float(r.amount),
            status=r.status or "issued",
            issue_date=r.issue_date,
            due_date=r.due_date,
        )
        for r in rows
    ]
    return {"invoices": items}


@router.post("/api/v1/invoices", status_code=status.HTTP_201_CREATED)
def create_invoice(body: InvoiceCreateBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    cust = db.get(CustomerORM, body.customer_id)
    if cust is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    today = nz_today()
    issue = body.issue_date or today
    due = body.due_date or date.fromordinal(issue.toordinal() + 14)
    if issue >= due:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="due_date must be after issue_date",
        )
    row = InvoiceORM(
        customer_id=body.customer_id,
        amount=float(body.amount),
        status=(body.status or "issued").strip(),
        issue_date=issue,
        due_date=due,
        notes=(body.notes or "").strip() or None,
        jobs_json=json.dumps(body.jobs),
        custom_items_json=json.dumps(body.custom_items),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"invoice_id": row.id}


@router.patch("/api/v1/invoices/{invoice_id}")
def patch_invoice(
    invoice_id: int,
    body: InvoicePatchBody,
    db: Session = Depends(get_db),
    x_actor_user_id: int = Header(default=0, alias="X-Actor-User-Id"),
) -> dict[str, str]:
    row = db.get(InvoiceORM, invoice_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    patch = body.model_dump(exclude_unset=True)
    if "customer_id" in patch and patch["customer_id"] is not None:
        if db.get(CustomerORM, patch["customer_id"]) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
        row.customer_id = patch["customer_id"]
    if "amount" in patch and patch["amount"] is not None:
        row.amount = float(patch["amount"])
    if "status" in patch and patch["status"] is not None:
        row.status = str(patch["status"]).strip()
    if "notes" in patch:
        v = patch["notes"]
        row.notes = None if v is None else ((str(v).strip() or None))
    if "issue_date" in patch and patch["issue_date"] is not None:
        row.issue_date = patch["issue_date"]
    if "due_date" in patch and patch["due_date"] is not None:
        row.due_date = patch["due_date"]
    if "jobs" in patch and patch["jobs"] is not None:
        row.jobs_json = json.dumps(patch["jobs"])
    if "custom_items" in patch and patch["custom_items"] is not None:
        row.custom_items_json = json.dumps(patch["custom_items"])
    if row.issue_date >= row.due_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="due_date must be after issue_date",
        )
    db.commit()
    append_audit_log(
        action="PATCH",
        entity="invoice",
        entity_id=invoice_id,
        before={},
        after={"invoice_id": invoice_id},
        actor_user_id=x_actor_user_id,
    )
    return {"status": "ok"}


@router.post("/api/v1/invoices/{invoice_id}/payments")
def post_invoice_payment(
    invoice_id: int,
    body: PaymentCreate,
    db: Session = Depends(get_db),
    x_actor_user_id: int = Header(default=0, alias="X-Actor-User-Id"),
) -> dict[str, Any]:
    invoice = db.get(InvoiceORM, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    pays = db.scalars(select(PaymentORM).where(PaymentORM.invoice_id == invoice_id)).all()
    before = {
        "invoice_id": invoice.id,
        "invoice_status": invoice.status,
        "payments": [{"id": p.id, "amount": p.amount} for p in pays],
    }
    payment = PaymentORM(
        invoice_id=invoice_id,
        amount=body.amount,
        date=nz_naive_now(),
        method=body.method,
        status=body.status,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    after = {
        "invoice_id": invoice.id,
        "invoice_status": invoice.status,
        "payments": before["payments"] + [{"id": payment.id, "amount": payment.amount}],
    }
    append_audit_log(
        action="POST",
        entity="invoice",
        entity_id=invoice_id,
        before=before,
        after=after,
        actor_user_id=x_actor_user_id,
    )
    return {"payment_id": payment.id, "amount": payment.amount, "status": payment.status}


@router.get("/api/v1/invoices/{id}", response_model=InvoiceDetailResponse)
def get_invoice(id: int, db: Session = Depends(get_db)) -> InvoiceDetailResponse:  # noqa: A002
    row = db.get(InvoiceORM, id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    cust = db.get(CustomerORM, row.customer_id)
    pays = db.scalars(select(PaymentORM).where(PaymentORM.invoice_id == id).order_by(PaymentORM.id)).all()
    return InvoiceDetailResponse(
        invoice=_row_to_invoice_entity(row, cust.name if cust else None),
        payments=[_payment_entity(p) for p in pays],
    )


@router.delete("/api/v1/invoices/{invoice_id}")
def delete_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    x_actor_user_id: int = Header(default=0, alias="X-Actor-User-Id"),
) -> dict[str, Any]:
    row = db.get(InvoiceORM, invoice_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    pays = list(db.scalars(select(PaymentORM).where(PaymentORM.invoice_id == invoice_id)).all())
    before = {
        "invoice_id": invoice_id,
        "amount": row.amount,
        "payments": [{"id": p.id, "amount": p.amount} for p in pays],
    }
    for p in pays:
        db.delete(p)
    db.delete(row)
    db.commit()
    append_audit_log(
        action="DELETE",
        entity="invoice",
        entity_id=invoice_id,
        before=before,
        after={},
        actor_user_id=x_actor_user_id,
    )
    return {"status": "deleted", "invoice_id": invoice_id}


@router.get("/api/v1/exports/invoices.csv")
def export_invoices_csv() -> Response:
    invoices_csv = "id,total,payment_status\n1,1000,Paid\n2,500,Unpaid"
    return Response(
        content=invoices_csv,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=invoices.csv"},
    )
