from __future__ import annotations

import unittest

import pytest
from fastapi.testclient import TestClient

from app.jobs_api import update_job
from app.main import app


class TestJobAPI(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_get_job_valid_id(self) -> None:
        response = self.client.get("/api/v1/jobs/1")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("property", data)
        self.assertIn("customer", data)

    def test_get_job_invalid_id(self) -> None:
        response = self.client.get("/api/v1/jobs/9999")
        self.assertEqual(response.status_code, 404)

    def test_delete_job_not_found(self) -> None:
        response = self.client.delete("/api/v1/jobs/99999")
        self.assertEqual(response.status_code, 404)

    def test_patch_job_assignee(self) -> None:
        r = self.client.patch("/api/v1/jobs/1", json={"assignee": "Jordan"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json().get("assignee"), "Jordan")
        got = self.client.get("/api/v1/jobs/1").json()
        self.assertEqual(got.get("assignee"), "Jordan")

    def test_patch_job_customer_refreshes_nested_customer(self) -> None:
        r = self.client.patch("/api/v1/jobs/1", json={"customer_id": 2, "property_id": 2})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data.get("customer_id"), 2)
        cust = data.get("customer") or {}
        self.assertEqual(cust.get("id"), 2)
        self.assertIn("name", cust)

    def test_patch_job_unknown_customer(self) -> None:
        r = self.client.patch("/api/v1/jobs/1", json={"customer_id": 99999})
        self.assertEqual(r.status_code, 404)

    def test_patch_job_estimated_minutes(self) -> None:
        r = self.client.patch("/api/v1/jobs/1", json={"estimated_duration_minutes": 90})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json().get("estimated_duration_minutes"), 90)
        got = self.client.get("/api/v1/jobs/1").json()
        self.assertEqual(got.get("estimated_duration_minutes"), 90)

    def test_patch_job_hours_worked(self) -> None:
        r = self.client.patch(
            "/api/v1/jobs/1",
            json={"workflow_status": "In Progress", "hours_worked": 2.5},
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data.get("hours_worked"), 2.5)
        self.assertEqual(data.get("workflow_status"), "In Progress")

    def test_patch_job_costs(self) -> None:
        body = {
            "job_costs": [
                {"category": "materials", "label": "Mulch", "amount": 45.5},
                {"category": "Paint supplies", "label": "Primer", "amount": 12},
            ],
        }
        r = self.client.patch("/api/v1/jobs/1", json=body)
        self.assertEqual(r.status_code, 200)
        costs = r.json().get("job_costs") or []
        self.assertEqual(len(costs), 2)
        self.assertEqual(costs[0]["category"], "materials")
        self.assertEqual(costs[0]["label"], "Mulch")
        self.assertEqual(costs[0]["amount"], 45.5)
        self.assertEqual(costs[1]["category"], "Paint supplies")
        self.assertEqual(costs[1]["amount"], 12.0)
        got = self.client.get("/api/v1/jobs/1").json().get("job_costs") or []
        self.assertEqual(len(got), 2)


def test_update_job_version_mismatch() -> None:
    with pytest.raises(ValueError, match="Version mismatch: Job has been modified by another user."):
        update_job(job_id=1, job_data={}, expected_version=1)


def test_post_job_complete_requires_idempotency_header() -> None:
    client = TestClient(app)
    body = {
        "actual_duration_minutes": 30,
        "checklist_results": [{"description": "Done", "completed": True}],
        "material_line_items": [{"material_id": 1, "quantity": 1.0}],
        "attachments": [],
        "completed_at": "2025-01-01T12:00:00Z",
        "system_status": "done",
    }
    r = client.post("/api/v1/jobs/1/complete", json=body)
    assert r.status_code == 400


def test_post_job_complete_idempotent_records_fields() -> None:
    client = TestClient(app)
    headers = {"Idempotency-Key": "task-79-key"}
    body = {
        "actual_duration_minutes": 45,
        "checklist_results": [{"description": "Mow lawn", "completed": True}],
        "material_line_items": [{"material_id": 2, "quantity": 3.5}],
        "attachments": [{"filename": "after.jpg", "file_url": "https://example.test/after.jpg"}],
        "completed_at": "2025-06-01T10:00:00Z",
        "system_status": "done",
    }
    r1 = client.post("/api/v1/jobs/1/complete", json=body, headers=headers)
    assert r1.status_code == 200
    data = r1.json()
    assert data['completion']['actual_duration_minutes'] == 45
    assert data["completion"]["system_status"] == "done"
    assert len(data["completion"]["checklist_results"]) == 1
    assert len(data["completion"]["material_line_items"]) == 1

    got = client.get("/api/v1/jobs/1").json()
    assert got["system_status"] == "done"
    assert got["completion"]["completed_at"] == "2025-06-01T10:00:00Z"

    r2 = client.post("/api/v1/jobs/1/complete", json=body, headers=headers)
    assert r2.status_code == 409


if __name__ == "__main__":
    unittest.main()