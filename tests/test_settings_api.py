from __future__ import annotations

from tests.http_helpers import auth_test_client

import json

from fastapi.testclient import TestClient

from app.main import app

client = auth_test_client()


def test_get_existing_setting() -> None:
    response = client.get("/api/v1/settings/services/pricing_tiers")
    assert response.status_code == 200
    data = response.json()
    assert "setting" in data
    assert data["setting"]["name"] == "services/pricing_tiers"
    assert json.loads(data["setting"]["current_value"]) == ["standard", "premium"]


def test_get_non_existing_setting() -> None:
    response = client.get("/api/v1/settings/branding/non_existing")
    assert response.status_code == 404
    assert response.json() == {"detail": "Setting not found"}


def test_get_existing_schema() -> None:
    response = client.get("/api/v1/settings/schemas/jobs")
    assert response.status_code == 200
    assert response.json() == {
        "schema": {"type": "object", "properties": {"name": {"type": "string"}}},
    }


def test_get_nonexistent_schema() -> None:
    response = client.get("/api/v1/settings/schemas/nonexistent")
    assert response.status_code == 404
    assert response.json() == {"detail": "Schema not found"}
