from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient

import app.customer_api as customer_api
from app.main import app

client = TestClient(app)


def test_import_customers_dry_run() -> None:
    before = len(customer_api._customers)
    csv_content = b"name,email\nDry,Dry@example.com\n"
    response = client.post(
        "/api/v1/imports/customers?dry_run=true",
        files={"file": ("customers.csv", BytesIO(csv_content), "text/csv")},
    )
    assert response.status_code == 200
    assert response.json().get("status") == "success"
    assert len(customer_api._customers) == before
    assert "dry run" in response.json().get("message", "").lower()
