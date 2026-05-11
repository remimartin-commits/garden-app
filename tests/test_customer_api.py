from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_customer_without_property() -> None:
    response = client.post("/api/v1/customers", json={"name": "John Doe", "email": "john@example.com"})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "John Doe"
    assert data["email"] == "john@example.com"
    assert data["properties"] == []


def test_create_customer_with_property() -> None:
    response = client.post(
        "/api/v1/customers",
        json={"name": "Jane Doe", "email": "jane@example.com", "property_address": "123 Garden St"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Jane Doe"
    assert data["email"] == "jane@example.com"
    assert len(data["properties"]) == 1
    assert data["properties"][0]["address"] == "123 Garden St"


def test_patch_customer_updates_contact_and_tags() -> None:
    created = client.post("/api/v1/customers", json={"name": "Pat", "email": "pat@example.com"})
    assert created.status_code == 200
    customer_id = created.json()["id"]
    response = client.patch(
        f"/api/v1/customers/{customer_id}",
        json={"contact_details": "Jane Doe", "tags": ["new"]},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["contact_details"] == "Jane Doe"
    assert data["tags"] == ["new"]
    assert "vip" not in data["tags"]


def test_archive_customer() -> None:
    created = client.post("/api/v1/customers", json={"name": "Test Customer", "email": "test@example.com"})
    assert created.status_code == 200
    customer_id = created.json()["id"]
    response = client.delete(f"/api/v1/customers/{customer_id}")
    assert response.status_code == 200
    assert response.json() == {"message": "Customer archived successfully"}
    gone = client.get(f"/api/v1/customers/{customer_id}")
    assert gone.status_code == 404


def test_delete_customer_retention_blocks_archive() -> None:
    created = client.post("/api/v1/customers", json={"name": "Held", "email": "held@example.com"})
    assert created.status_code == 200
    customer_id = created.json()["id"]
    patch = client.patch(f"/api/v1/customers/{customer_id}", json={"tags": ["retention_hold"]})
    assert patch.status_code == 200
    response = client.delete(f"/api/v1/customers/{customer_id}")
    assert response.status_code == 409
    assert "retention" in response.json()["detail"].lower()


@pytest.mark.skip(reason="POST /api/v1/properties is not implemented in this FastAPI app (legacy Flask test).")
def test_add_service_property() -> None:
    """Placeholder: previously targeted Flask ``/api/v1/properties`` via ``ServiceProperty``."""
    raise AssertionError("unreachable when not skipped")


def test_import_customers_csv() -> None:
    from io import BytesIO

    csv_content = b"name,email,phone\nImport,import@example.com,\n"
    response = client.post(
        "/api/v1/imports/customers",
        files={"file": ("customers.csv", BytesIO(csv_content), "text/csv")},
    )
    assert response.status_code == 200
    assert response.json().get("status") == "success"
