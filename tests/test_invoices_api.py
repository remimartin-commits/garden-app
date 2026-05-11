from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_get_invoice_returns_invoice_and_payments(client: TestClient) -> None:
    response = client.get("/api/v1/invoices/1")
    assert response.status_code == 200
    data = response.json()
    assert "invoice" in data
    assert "payments" in data
    assert data["invoice"]["invoice_id"] == 1
    assert isinstance(data["payments"], list)


def test_get_invoice_not_found(client: TestClient) -> None:
    assert client.get("/api/v1/invoices/9999").status_code == 404


def test_list_invoices_contains_demo(client: TestClient) -> None:
    r = client.get("/api/v1/invoices")
    assert r.status_code == 200
    data = r.json()
    assert "invoices" in data
    assert any(inv.get("invoice_id") == 1 for inv in data["invoices"])


def test_delete_invoice_not_found(client: TestClient) -> None:
    assert client.delete("/api/v1/invoices/99999").status_code == 404


def test_create_and_patch_invoice(client: TestClient) -> None:
    c = client.post("/api/v1/invoices", json={"customer_id": 1, "amount": 99.5, "status": "issued"})
    assert c.status_code == 201
    iid = c.json()["invoice_id"]
    p = client.patch(
        f"/api/v1/invoices/{iid}",
        json={"amount": 120.0, "status": "paid", "notes": "Paid in full"},
    )
    assert p.status_code == 200
    g = client.get(f"/api/v1/invoices/{iid}")
    assert g.status_code == 200
    inv = g.json()["invoice"]
    assert inv["amount"] == 120.0
    assert inv["status"].lower() == "paid"
    assert inv["notes"] == "Paid in full"


def test_delete_invoice_removes_row(client: TestClient) -> None:
    c = client.post("/api/v1/invoices", json={"customer_id": 1, "amount": 10.0, "status": "draft"})
    assert c.status_code == 201
    iid = c.json()["invoice_id"]
    d = client.delete(f"/api/v1/invoices/{iid}")
    assert d.status_code == 200
    assert client.get(f"/api/v1/invoices/{iid}").status_code == 404
