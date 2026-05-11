from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


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


def test_delete_sample_rule_rejected() -> None:
    response = client.delete("/api/v1/recurring-job-rules/1")
    assert response.status_code == 400


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
