from fastapi.testclient import TestClient

from app.entities import DashboardMetrics
from app.main import app


def test_root_redirects_to_autonomy_dashboard():
    client = TestClient(app)
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers.get("location") == "/static/autonomy.html"


def test_demo_pool_serves_pool_marketing_page():
    client = TestClient(app)
    r = client.get("/demo/pool")
    assert r.status_code == 200
    assert "NZ Pool Installers" in r.text
    assert "Nationwide swimming pool" in r.text
