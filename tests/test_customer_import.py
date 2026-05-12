from __future__ import annotations

from tests.http_helpers import auth_test_client

from pathlib import Path

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Customer as CustomerORM

client = auth_test_client()


def _customer_count() -> int:
    db = SessionLocal()
    try:
        return db.query(CustomerORM).count()
    finally:
        db.close()


def test_import_customers(tmp_path: Path) -> None:
    before_ids = _customer_count()
    csv_path = tmp_path / "customers.csv"
    csv_path.write_text(
        "name,email,phone,address\n"
        "Import User,import@example.com,555-0100,99 Import Rd\n",
        encoding="utf-8",
    )
    with csv_path.open("rb") as csv_file:
        response = client.post(
            "/api/v1/imports/customers",
            files={"file": ("customers.csv", csv_file, "text/csv")},
        )
    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "message": "Customers and properties imported successfully.",
    }
    assert _customer_count() == before_ids + 1
    db = SessionLocal()
    try:
        emails = [r.email for r in db.query(CustomerORM).all()]
    finally:
        db.close()
    assert "import@example.com" in emails
