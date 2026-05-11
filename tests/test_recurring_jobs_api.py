from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_recurring_job_rule_success() -> None:
    response = client.post(
        "/api/v1/recurring-job-rules",
        json={
            "property_id": 1,
            "frequency": "weekly",
            "start_date": "2023-10-01",
            "notes": "Mow lawns every week",
        },
    )
    assert response.status_code == 201
    assert response.json() == {"message": "Recurring job rule created successfully."}


def test_create_recurring_job_rule_missing_property_id() -> None:
    response = client.post(
        "/api/v1/recurring-job-rules",
        json={
            "frequency": "weekly",
            "start_date": "2023-10-01",
        },
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Property ID is required"}
