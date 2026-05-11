from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.mark.parametrize("endpoint", ["/api/v1/exports/jobs.csv", "/api/v1/exports/invoices.csv"])
def test_export_csv_endpoints(endpoint: str) -> None:
    response = client.get(endpoint)
    assert response.status_code == 200
    assert "text/csv" in response.headers.get("content-type", "")


def test_export_jobs_csv() -> None:
    response = client.get("/api/v1/exports/jobs.csv")
    assert response.status_code == 200
    assert len(response.content) > 0


def test_export_invoices_csv() -> None:
    response = client.get("/api/v1/exports/invoices.csv")
    assert response.status_code == 200
    assert len(response.content) > 0
