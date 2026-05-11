from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_logout_successful() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": "Bearer test-session"},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Logout successful"


def test_logout_not_authenticated() -> None:
    client = TestClient(app)
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 401
    assert response.json()["error"] == "Not authenticated"


def test_password_reset_request() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/password-reset",
        json={"email": "user@example.com"},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Password reset request received"


def test_password_reset_completion() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/password-reset",
        json={"token": "valid_token", "new_password": "new_strong_password"},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Password has been reset successfully"


def test_password_reset_invalid_request() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/password-reset",
        json={"username": "invalid"},
    )
    assert response.status_code == 400
    assert "error" in response.json()
