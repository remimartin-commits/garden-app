from __future__ import annotations

import os

from fastapi.testclient import TestClient

from app.main import app


def test_api_returns_401_when_not_logged_in() -> None:
    client = TestClient(app)
    r = client.get("/api/v1/dashboard")
    assert r.status_code == 401
    assert r.json().get("detail") == "Not authenticated"


def test_login_success_sets_session() -> None:
    client = TestClient(app)
    user = os.environ.get("OWNER_USERNAME", "owner")
    password = os.environ["OWNER_PASSWORD"]
    r = client.post(
        "/login",
        data={"username": user, "password": password},
        follow_redirects=False,
    )
    assert r.status_code == 302
    dash = client.get("/api/v1/dashboard")
    assert dash.status_code == 200


def test_login_failure_returns_401_page() -> None:
    client = TestClient(app)
    r = client.post(
        "/login",
        data={"username": "nope", "password": "bad"},
        follow_redirects=False,
    )
    assert r.status_code == 401


def test_logout_clears_session() -> None:
    client = TestClient(app)
    user = os.environ.get("OWNER_USERNAME", "owner")
    password = os.environ["OWNER_PASSWORD"]
    client.post("/login", data={"username": user, "password": password}, follow_redirects=False)
    assert client.get("/api/v1/dashboard").status_code == 200
    out = client.post("/logout", follow_redirects=False)
    assert out.status_code == 302
    assert client.get("/api/v1/dashboard").status_code == 401
