from __future__ import annotations

from tests.http_helpers import auth_test_client
import pytest
from app.main import app
from starlette.testclient import TestClient
from app.entities import Job

client = auth_test_client()

def test_get_job_details():
    response = client.get("/api/v1/jobs/1")
    assert response.status_code == 200
    data = response.json()
    assert "property_info" in data
    assert "customer_id" in data
    assert "checklist" in data
    assert "materials" in data
    assert "attachments" in data
    assert "weather_context" in data
    assert "estimated_duration_minutes" in data
    assert "hours_worked" in data
