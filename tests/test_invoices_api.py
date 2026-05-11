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
