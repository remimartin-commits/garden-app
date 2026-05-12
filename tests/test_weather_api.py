from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_weather_returns_forecast_and_snapshots() -> None:
    response = client.get("/api/v1/weather")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert "summary" in data
    assert isinstance(data["summary"], str)
    assert data.get("timezone") == "Pacific/Auckland"
    snaps = data.get("snapshots")
    assert isinstance(snaps, list)
    assert len(snaps) >= 1
    suburbs = {str(row.get("suburb", "")).lower() for row in snaps}
    assert any("redcliffs" in s or "christchurch" in s for s in suburbs)
    first = snaps[0]
    assert "weather_snapshot_id" in first
    for key in ("temperature", "humidity", "wind_speed", "description", "timestamp"):
        assert key in first
    fc = data.get("forecast")
    assert isinstance(fc, list)
    assert len(fc) == 14
    day0 = fc[0]
    for key in ("date", "weekday", "label", "high_c", "low_c", "precipitation_probability", "wind_kmh"):
        assert key in day0


def test_get_weather_snapshots_nested() -> None:
    response = client.get("/api/v1/weather")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body.get("snapshots"), list)


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
