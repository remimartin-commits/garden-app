from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_reschedule_weather_risk() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v1/schedule/reschedule-weather-risk",
        json={"weatherRisk": "rain", "rescheduleOption": True},
    )
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "Jobs rescheduled successfully"
    assert isinstance(data.get("affected_jobs"), list)
