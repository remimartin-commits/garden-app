from __future__ import annotations
import pytest
from app.main import app
from starlette.testclient import TestClient
from app.entities import Job

client = TestClient(app)

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
