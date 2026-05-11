from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Customer as CustomerORM

client = TestClient(app)


def _customer_count() -> int:
    db = SessionLocal()
    try:
        return db.query(CustomerORM).count()
    finally:
        db.close()


def test_import_customers_dry_run() -> None:
    before = _customer_count()
    csv_content = b"name,email\nDry,Dry@example.com\n"
    response = client.post(
        "/api/v1/imports/customers?dry_run=true",
        files={"file": ("customers.csv", BytesIO(csv_content), "text/csv")},
    )
    assert response.status_code == 200
    assert response.json().get("status") == "success"
    assert _customer_count() == before
    assert "dry run" in response.json().get("message", "").lower()
