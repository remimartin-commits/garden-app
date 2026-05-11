
from __future__ import annotations
from fastapi.testclient import TestClient
from app.main import app
from app.entities import Job

client = TestClient(app)

def test_export_jobs_csv():
    response = client.get("/api/v1/exports/jobs.csv")
    assert response.status_code == 200
    assert response.headers["Content-Disposition"] == "attachment; filename=jobs.csv"
    assert response.headers["Content-Type"].startswith("text/csv")
