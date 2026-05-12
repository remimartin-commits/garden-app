from __future__ import annotations

from tests.http_helpers import auth_test_client

from fastapi.testclient import TestClient

from app.main import app


def test_create_customer_with_property() -> None:
    client = auth_test_client()
    response = client.post(
        "/api/v1/customers",
        json={
            "name": "John Doe",
            "email": "john@example.com",
            "property_address": "123 Garden Lane",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert data["name"] == "John Doe"
    assert len(data.get("properties", [])) == 1
    assert data["properties"][0]["address"] == "123 Garden Lane"
