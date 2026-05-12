from __future__ import annotations

from tests.http_helpers import auth_test_client

from fastapi.testclient import TestClient

from app.main import app

client = auth_test_client()


def test_create_recurring_job_rule_success() -> None:
    response = client.post(
        "/api/v1/recurring-job-rules",
        json={
            "property_id": 1,
            "frequency": "weekly",
            "start_date": "2023-10-01",
            "notes": "Mow lawns every week",
        },
    )
    assert response.status_code == 201
    assert response.json() == {"message": "Recurring job rule created successfully."}


def test_create_recurring_job_rule_missing_property_id() -> None:
    response = client.post(
        "/api/v1/recurring-job-rules",
        json={
            "frequency": "weekly",
            "start_date": "2023-10-01",
        },
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Property ID is required"}


def test_list_recurring_job_rules_includes_sample() -> None:
    response = client.get("/api/v1/recurring-job-rules")
    assert response.status_code == 200
    rules = response.json()["rules"]
    assert any(r["id"] == 1 for r in rules)
    sample = next(r for r in rules if r["id"] == 1)
    assert sample["cadence"] == "weekly"
    assert sample.get("property_id") == 201
    assert sample.get("property_address") == "14 Marine Parade, Mt Maunganui"
    assert "extra_costs" in sample
    assert sample["extra_costs"] == []
    assert sample.get("instances_worked") == 0
    assert sample.get("hours_per_instance") is None


def test_patch_recurring_rule_extra_costs() -> None:
    r = client.patch(
        "/api/v1/recurring-job-rules/1",
        json={"extra_costs": [{"category": "materials", "label": "Blades", "amount": 15}]},
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data.get("extra_costs") or []) == 1
    assert data["extra_costs"][0]["amount"] == 15.0


def test_patch_recurring_rule_instances_and_hours() -> None:
    r = client.patch(
        "/api/v1/recurring-job-rules/1",
        json={"instances_worked": 5, "hours_per_instance": 2.5},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["instances_worked"] == 5
    assert data["hours_per_instance"] == 2.5
    r2 = client.patch("/api/v1/recurring-job-rules/1", json={"hours_per_instance": None})
    assert r2.status_code == 200
    assert r2.json().get("hours_per_instance") is None


def test_create_patch_delete_recurring_rule_roundtrip() -> None:
    create = client.post(
        "/api/v1/recurring-job-rules",
        json={
            "property_id": 99,
            "frequency": "monthly",
            "start_date": "2026-03-10",
            "notes": "Hedge trim cycle",
            "day_of_month": 15,
        },
    )
    assert create.status_code == 201
    lst = client.get("/api/v1/recurring-job-rules").json()["rules"]
    rid = max(r["id"] for r in lst)
    patch = client.patch(
        f"/api/v1/recurring-job-rules/{rid}",
        json={"description": "Updated hedge", "cadence": "weekly", "day_of_week": 2},
    )
    assert patch.status_code == 200
    assert patch.json()["description"] == "Updated hedge"
    assert patch.json()["cadence"] == "weekly"
    preview = client.post(f"/api/v1/recurring-job-rules/{rid}/preview")
    assert preview.status_code == 200
    assert len(preview.json()) == 5
    deleted = client.delete(f"/api/v1/recurring-job-rules/{rid}")
    assert deleted.status_code == 204
    missing = client.get(f"/api/v1/recurring-job-rules/{rid}")
    assert missing.status_code == 404
