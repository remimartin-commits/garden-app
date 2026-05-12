from __future__ import annotations

import os

if not (os.environ.get("OWNER_PASSWORD") or "").strip():
    os.environ["OWNER_PASSWORD"] = "pytest-garden-auth-secret"

from fastapi.testclient import TestClient

from app import config
from app.main import app


def auth_test_client() -> TestClient:
    """TestClient with session cookie when the auth gate is enabled."""
    c = TestClient(app)
    if not config.auth_gate_enabled():
        return c
    user = (os.environ.get("OWNER_USERNAME") or "owner").strip()
    password = os.environ["OWNER_PASSWORD"]
    r = c.post(
        "/login",
        data={"username": user, "password": password},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303), r.text
    return c
