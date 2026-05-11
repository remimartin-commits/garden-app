from __future__ import annotations
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _first_service_slug():
    response = client.get("/api/services")
    assert response.status_code == 200
    payload = response.json()
    services = payload.get("services") if isinstance(payload, dict) else payload
    assert isinstance(services, list)
    assert services, "Expected at least one service in /api/services"

    for service in services:
        if isinstance(service, dict) and service.get("slug"):
            return service["slug"]

    raise AssertionError("Expected a service with a slug in /api/services")


def test_service_detail_returns_schema_wrapped_service():
    slug = _first_service_slug()

    response = client.get(f"/api/services/{slug}")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {"service"}

    service = payload["service"]
    assert service["slug"] == slug
    assert isinstance(service.get("name"), str)
    assert service["name"].strip()
    assert isinstance(service.get("description"), str)
    assert service["description"].strip()

    # Legacy flat/non-schema fields must not leak into the API detail contract.
    assert "title" not in service
    assert "audience" not in service
    assert "coverage" not in service


def test_service_detail_unknown_slug_returns_404():
    response = client.get("/api/services/not-a-real-service-slug")

    assert response.status_code == 404
