from fastapi.testclient import TestClient

from app.main import app
from tests.http_helpers import auth_test_client


def test_root_redirects_unauthenticated_to_login() -> None:
    client = TestClient(app)
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 302
    loc = r.headers.get("location") or ""
    assert loc.startswith("/login")


def test_root_serves_app_when_authenticated() -> None:
    client = auth_test_client()
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 200
    assert "GreenOps" in r.text
