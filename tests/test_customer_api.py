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
    assert float(data.get("fuel_cost", 0)) == 10.0


def test_create_customer_with_custom_fuel_cost() -> None:
    response = client.post(
        "/api/v1/customers",
        json={"name": "Fuelie", "email": "fuelie@example.com", "fuel_cost": 18.5},
    )
    assert response.status_code == 200
    assert response.json()["fuel_cost"] == 18.5


def test_patch_customer_fuel_cost() -> None:
    created = client.post("/api/v1/customers", json={"name": "Van", "email": "van@example.com"})
    assert created.status_code == 200
    cid = created.json()["id"]
    assert float(created.json().get("fuel_cost", 0)) == 10.0
    r = client.patch(f"/api/v1/customers/{cid}", json={"fuel_cost": 22.0})
    assert r.status_code == 200
    assert r.json()["fuel_cost"] == 22.0


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


def test_patch_customer_success_updates_name_email_phone() -> None:
    created = client.post(
        "/api/v1/customers",
        json={"name": "Alex", "email": "alex@example.com", "phone": "111"},
    )
    assert created.status_code == 200
    customer_id = created.json()["id"]
    response = client.patch(
        f"/api/v1/customers/{customer_id}",
        json={"name": "Alexis", "email": "alexis@example.com", "phone": "222"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Alexis"
    assert data["email"] == "alexis@example.com"
    assert data["phone"] == "222"


def test_patch_customer_partial_update_name_only_preserves_other_fields() -> None:
    created = client.post(
        "/api/v1/customers",
        json={"name": "Bob", "email": "bob@example.com", "phone": "555"},
    )
    assert created.status_code == 200
    customer_id = created.json()["id"]
    response = client.patch(
        f"/api/v1/customers/{customer_id}",
        json={"name": "Robert"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Robert"
    assert data["email"] == "bob@example.com"
    assert data["phone"] == "555"
    assert float(data.get("fuel_cost", 0)) == 10.0


def test_create_customer_with_hourly_price_agreed() -> None:
    response = client.post(
        "/api/v1/customers",
        json={
            "name": "Priced",
            "email": "priced@example.com",
            "price_agreed_type": "hourly",
            "price_agreed_amount": 120.5,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["price_agreed_type"] == "hourly"
    assert data["price_agreed_amount"] == 120.5


def test_create_customer_price_defaults_to_fixed_per_job() -> None:
    response = client.post(
        "/api/v1/customers",
        json={"name": "Fixed", "email": "fixed@example.com", "price_agreed_amount": 450.0},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["price_agreed_type"] == "fixed"
    assert data["price_agreed_amount"] == 450.0


def test_patch_customer_price_agreed_set_and_clear() -> None:
    created = client.post("/api/v1/customers", json={"name": "Deal", "email": "deal@example.com"})
    assert created.status_code == 200
    customer_id = created.json()["id"]
    set_price = client.patch(
        f"/api/v1/customers/{customer_id}",
        json={"price_agreed_type": "hourly", "price_agreed_amount": 89.0},
    )
    assert set_price.status_code == 200
    assert set_price.json()["price_agreed_type"] == "hourly"
    assert set_price.json()["price_agreed_amount"] == 89.0
    clear = client.patch(f"/api/v1/customers/{customer_id}", json={"price_agreed_amount": None})
    assert clear.status_code == 200
    assert clear.json().get("price_agreed_amount") is None
    assert clear.json().get("price_agreed_type") is None


def test_patch_customer_not_found_returns_404() -> None:
    response = client.patch("/api/v1/customers/999999999", json={"name": "Ghost"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Customer not found"


def test_patch_customer_property_address_updates_primary_property() -> None:
    created = client.post(
        "/api/v1/customers",
        json={"name": "Site", "email": "site@example.com", "property_address": "Old Road"},
    )
    assert created.status_code == 200
    customer_id = created.json()["id"]
    response = client.patch(
        f"/api/v1/customers/{customer_id}",
        json={"property_address": "New Road"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["properties"]) == 1
    assert data["properties"][0]["address"] == "New Road"


def test_patch_customer_property_address_creates_primary_when_missing() -> None:
    created = client.post("/api/v1/customers", json={"name": "NoProp", "email": "noprop@example.com"})
    assert created.status_code == 200
    customer_id = created.json()["id"]
    assert created.json()["properties"] == []
    response = client.patch(
        f"/api/v1/customers/{customer_id}",
        json={"property_address": "99 Oak Avenue"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["properties"]) == 1
    assert data["properties"][0]["address"] == "99 Oak Avenue"


def test_patch_customer_tags_and_property_without_touching_email() -> None:
    created = client.post(
        "/api/v1/customers",
        json={"name": "Tagger", "email": "tagger@example.com", "property_address": "1 A St"},
    )
    assert created.status_code == 200
    customer_id = created.json()["id"]
    response = client.patch(
        f"/api/v1/customers/{customer_id}",
        json={"tags": ["vip", "quarterly"], "property_address": "2 B St"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "tagger@example.com"
    assert data["tags"] == ["vip", "quarterly"]
    assert data["properties"][0]["address"] == "2 B St"


def test_archive_customer() -> None:
    created = client.post("/api/v1/customers", json={"name": "Test Customer", "email": "test@example.com"})
    assert created.status_code == 200
    customer_id = created.json()["id"]
    response = client.delete(f"/api/v1/customers/{customer_id}")
    assert response.status_code == 200
    assert response.json() == {"message": "Customer archived successfully"}
    gone = client.get(f"/api/v1/customers/{customer_id}")
    assert gone.status_code == 404
    listed = client.get("/api/v1/customers").json()["customers"]
    assert all(int(c["id"]) != int(customer_id) for c in listed)


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
