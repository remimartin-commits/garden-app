from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_autonomy_status_route_registered() -> None:
    client = TestClient(app)
    response = client.get("/autonomy/status")
    assert response.status_code == 200


def test_read_recurring_job_rule_success() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/recurring-job-rules/1")
    assert response.status_code == 200
    assert response.json() == {"id": 1, "name": "Weekly Lawn Mowing"}


def test_read_recurring_job_rule_not_found() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/recurring-job-rules/999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Recurring job rule not found"}
