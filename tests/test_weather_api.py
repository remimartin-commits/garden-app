from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_weather_returns_cached_snapshots_for_christchurch_area() -> None:
    response = client.get("/api/v1/weather")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    suburbs = {str(row.get("suburb", "")).lower() for row in data}
    assert any("redcliffs" in s or "christchurch" in s for s in suburbs)
    first = data[0]
    assert "weather_snapshot_id" in first
    for key in ("temperature", "humidity", "wind_speed", "description", "timestamp"):
        assert key in first


def test_get_weather_snapshots() -> None:
    response = client.get("/api/v1/weather")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_reschedule_weather_risk() -> None:
    response = client.post("/api/v1/schedule/reschedule-weather-risk")
    assert response.status_code == 200
    body = response.json()
    assert body.get("status") == "Jobs rescheduled successfully"
    jobs = body.get("affected_jobs")
    assert isinstance(jobs, list)
    assert len(jobs) >= 1
    for row in jobs:
        assert "job_id" in row
        assert row.get("weather_snapshot_id") is not None or bool(row.get("risk_advice"))
