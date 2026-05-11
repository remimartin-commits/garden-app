from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Header, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict

from app.audit_api import append_audit_log
from app.entities import Invoice, Payment

router = APIRouter(tags=["invoices"])

_invoices: dict[int, Invoice] = {}
_payments: dict[int, list[Payment]] = {}


class InvoiceDetailResponse(BaseModel):
    """Schema-aligned wrapper for GET /api/v1/invoices/{id}."""

    model_config = ConfigDict(from_attributes=True)

    invoice: Invoice
    payments: list[Payment]


def _seed_demo_invoice() -> None:
    if _invoices:
        return
    today = date.today()
    due = date.fromordinal(today.toordinal() + 14)
    inv = Invoice(
        invoice_id=1,
        customer_id=101,
        amount=250.0,
        status="issued",
        issue_date=today,
        due_date=due,
        jobs=[1, 2],
        custom_items=[],
    )
    _invoices[1] = inv
    _payments[1] = [
        Payment(
            id=1,
            amount=50.0,
            date=datetime.now(timezone.utc),
            method="bank_transfer",
            status="Completed",
            invoice_id=1,
        ),
    ]


_seed_demo_invoice()


class PaymentCreate(BaseModel):
    amount: float
    method: str = "bank_transfer"
    status: str = "Completed"


@router.post("/api/v1/invoices/{invoice_id}/payments")
def post_invoice_payment(
    invoice_id: int,
    body: PaymentCreate,
    x_actor_user_id: int = Header(default=0, alias="X-Actor-User-Id"),
) -> dict[str, Any]:
    invoice = _invoices.get(invoice_id)
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    before = {
        "invoice_id": invoice.invoice_id,
        "invoice_status": invoice.status,
        "payments": [{"id": p.id, "amount": p.amount} for p in _payments.get(invoice_id, [])],
    }
    next_id = 1
    for plist in _payments.values():
        for p in plist:
            next_id = max(next_id, p.id + 1)
    payment = Payment(
        id=next_id,
        amount=body.amount,
        date=datetime.now(timezone.utc),
        method=body.method,
        status=body.status,
        invoice_id=invoice_id,
    )
    _payments.setdefault(invoice_id, []).append(payment)
    after = {
        "invoice_id": invoice.invoice_id,
        "invoice_status": invoice.status,
        "payments": [{"id": p.id, "amount": p.amount} for p in _payments.get(invoice_id, [])],
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
def get_invoice(id: int) -> InvoiceDetailResponse:  # noqa: A002
    """Return one invoice and its recorded payments (in-memory demo store)."""
    invoice = _invoices.get(id)
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    payments = list(_payments.get(id, []))
    return InvoiceDetailResponse(invoice=invoice, payments=payments)


@router.get("/api/v1/exports/invoices.csv")
def export_invoices_csv() -> Response:
    invoices_csv = "id,total,payment_status\n1,1000,Paid\n2,500,Unpaid"
    return Response(
        content=invoices_csv,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=invoices.csv"},
    )