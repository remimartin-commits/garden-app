from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth import authenticate_user, verify_owner_credentials


def test_verify_owner_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.OWNER_USERNAME", "owner")
    monkeypatch.setattr("app.config.OWNER_PASSWORD", "secret")
    assert verify_owner_credentials("owner", "secret") is True
    assert verify_owner_credentials("owner", "wrong") is False
    assert verify_owner_credentials("other", "secret") is False


def test_authenticate_user_matches_verify(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.OWNER_USERNAME", "owner")
    monkeypatch.setattr("app.config.OWNER_PASSWORD", "correct_password")
    assert authenticate_user("owner", "correct_password") is not None
    assert authenticate_user("owner", "wrong") is None


def test_login_page_reachable_without_session() -> None:
    from app.main import app

    client = TestClient(app)
    r = client.get("/login")
    assert r.status_code == 200
    assert "GreenOps" in r.text
