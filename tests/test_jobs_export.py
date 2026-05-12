from __future__ import annotations

from tests.http_helpers import auth_test_client

from app.entities import Job

client = auth_test_client()


def test_export_jobs_csv() -> None:
    response = client.get("/api/v1/exports/jobs.csv")
    assert response.status_code == 200
    assert response.headers["Content-Disposition"] == "attachment; filename=jobs.csv"
    assert response.headers["Content-Type"].startswith("text/csv")
