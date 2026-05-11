from fastapi.testclient import TestClient

from app.main import app
from app.entities import DashboardMetrics
from app.entities import Job, Quote

client = TestClient(app)


def test_get_service_by_slug_returns_service_detail():
    response = client.get("/api/services/consultation-design")

    assert response.status_code == 200
    data = response.json()
    svc = data["service"]
    assert svc["slug"] == "consultation-design"
    assert svc["name"] == "Pool Consultation & Design"
    assert "description" in svc
    assert isinstance(svc["stages"], list)


def test_get_service_by_unknown_slug_returns_404():
    response = client.get("/api/services/not-a-real-service")

    assert response.status_code == 404
    assert response.json()["detail"] == "Service not found"


def test_delete_service_template_soft_archives() -> None:
    response = client.delete("/api/v1/service-templates/some-template-id")
    assert response.status_code == 200
    assert response.json() == {"status": "archived"}

    response = client.delete("/api/v1/service-templates/non-existent")
    assert response.status_code == 404