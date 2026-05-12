from __future__ import annotations

from tests.http_helpers import auth_test_client

from fastapi.testclient import TestClient

from app.main import app

client = auth_test_client()


def test_reschedule_weather_risk() -> None:
    response = client.post("/api/v1/schedule/reschedule-weather-risk")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "Jobs rescheduled successfully"
    assert isinstance(data.get("affected_jobs"), list)
