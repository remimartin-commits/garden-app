from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_audit_logs() -> None:
    response = client.get("/api/v1/audit-logs", params={"entity": "Customer", "actor": "Admin"})
    assert response.status_code == 200
    assert response.json() == {
        "logs": [
            {
                "entity": "Customer",
                "actor": "Admin",
                "action": "Update",
                "date": "2023-10-05",
            }
        ],
    }


def test_get_audit_logs_with_filters() -> None:
    response = client.get("/api/v1/audit-logs", params={"entity": "job", "actor": "admin"})
    assert response.status_code == 200
    data = response.json()["logs"]
    assert len(data) == 1
    assert data[0]["entity"] == "job"
    assert data[0]["actor"] == "admin"
