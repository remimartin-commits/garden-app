from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import app.customer_api as customer_api
from app.main import app

client = TestClient(app)


def test_import_customers(tmp_path: Path) -> None:
    before_ids = len(customer_api._customers)
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
    assert len(customer_api._customers) == before_ids + 1
    assert any(c.email == "import@example.com" for c in customer_api._customers.values())
