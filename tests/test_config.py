from __future__ import annotations

from tests.http_helpers import auth_test_client

from fastapi.testclient import TestClient

from app.main import app

client = auth_test_client()


def test_get_setting_success() -> None:
    response = client.get("/api/v1/settings/services/pricing")
    assert response.status_code == 200
    data = response.json()
    assert data["setting"]["current_value"] == "variable"


def test_get_setting_category_not_found() -> None:
    response = client.get("/api/v1/settings/nonexistent/pricing")
    assert response.status_code == 404
    assert response.json() == {"detail": "Setting not found"}


def test_get_setting_key_not_found() -> None:
    response = client.get("/api/v1/settings/services/nonexistent")
    assert response.status_code == 404
    assert response.json() == {"detail": "Setting not found"}
