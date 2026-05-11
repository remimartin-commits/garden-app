from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.auth import authenticate_user
from app.entities import AuthSession


@pytest.mark.parametrize(
    "username,password,expected",
    [
        ("owner", "correct_password", True),
        ("archived", "any_password", False),
    ],
)
def test_authenticate_user(username: str, password: str, expected: bool) -> None:
    token = authenticate_user(username, password)
    assert (token is not None) == expected


def test_login_valid_user_returns_token(client: TestClient) -> None:
    response = client.post("/api/v1/auth/login", json={"username": "valid_user", "password": "password"})
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_archived_user_rejected(client: TestClient) -> None:
    response = client.post("/api/v1/auth/login", json={"username": "archived_user", "password": "password"})
    assert response.status_code == 401
    assert "access_token" not in response.json()


def test_logout(client: TestClient) -> None:
    session = AuthSession(
        session_id="123",
        user_id="user_123",
        created_at=datetime.now(),
        expires_at=datetime.now(),
    )
    response = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {session.session_id}"},
    )
    assert response.status_code == 200
    assert response.json() == {"message": "Logout successful"}
