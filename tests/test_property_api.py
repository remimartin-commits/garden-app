from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_property_by_id_returns_service_property() -> None:
    response = client.get("/api/v1/properties/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["customer_id"] == 1
    assert data["address"] == "123 Garden Lane"
    assert data["service_history"] == ["Initial site assessment"]


def test_get_property_unknown_id_returns_404() -> None:
    response = client.get("/api/v1/properties/99999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_delete_property_soft_archives() -> None:
    response = client.delete("/api/v1/properties/1")
    assert response.status_code == 200
    assert response.json() == {"message": "Property archived successfully"}
    assert client.get("/api/v1/properties/1").status_code == 404


def test_delete_property_retention_blocks_when_tagged() -> None:
    """Property ``2`` is seeded with ``retention_hold`` (see ``app.property_api``)."""
    assert client.get("/api/v1/properties/2").status_code == 200
    response = client.delete("/api/v1/properties/2")
    assert response.status_code == 409
    assert "retention" in response.json()["detail"].lower()
    assert client.get("/api/v1/properties/2").status_code == 200
