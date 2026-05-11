from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_preview_recurring_jobs() -> None:
    response = client.post("/api/v1/recurring-job-rules/1/preview")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 5
    assert data[0]["parent_recurring_rule_id"] == 1
    assert "generated_for_date" in data[0]


def test_pause_job_rule() -> None:
    response = client.post("/api/v1/recurring-job-rules/1/pause", json={"pause": True})
    assert response.status_code == 200
    assert response.json() == {"status": "success", "job_rule_id": 1, "paused": True}


def test_resume_job_rule() -> None:
    response = client.post("/api/v1/recurring-job-rules/1/pause", json={"pause": False})
    assert response.status_code == 200
    assert response.json() == {"status": "success", "job_rule_id": 1, "paused": False}


def test_pause_nonexistent_job_rule() -> None:
    response = client.post("/api/v1/recurring-job-rules/99/pause", json={"pause": True})
    assert response.status_code == 404
    assert response.json() == {"detail": "Recurring job rule not found"}
