from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_audit_logs_endpoint_returns_logs() -> None:
    response = client.get("/api/v1/audit-logs")
    assert response.status_code == 200
    body = response.json()
    assert "logs" in body
    assert isinstance(body["logs"], list)


def _find_latest_audit(*, action: str, entity: str) -> dict:
    logs = client.get("/api/v1/audit-logs").json()["logs"]
    matches = [x for x in logs if x.get("action") == action and str(x.get("entity", "")).lower() == entity.lower()]
    assert matches, f"no audit for action={action} entity={entity}"
    return matches[-1]


def test_mutating_endpoints_emit_audit_entries() -> None:
    headers = {"X-Actor-User-Id": "42"}

    r_job = client.patch("/api/v1/jobs/1", json={"workflow_status": "In progress"}, headers=headers)
    assert r_job.status_code == 200
    e_job = _find_latest_audit(action="PATCH", entity="job")
    for key in ("before", "after", "actor_user_id", "created_at"):
        assert key in e_job
    assert e_job["actor_user_id"] == 42

    client.patch("/api/v1/jobs/1", json={"workflow_status": "Scheduled"}, headers=headers)

    r_pay = client.post(
        "/api/v1/invoices/1/payments",
        json={"amount": 10.0, "method": "card", "status": "Completed"},
        headers=headers,
    )
    assert r_pay.status_code == 200
    e_inv = _find_latest_audit(action="POST", entity="invoice")
    for key in ("before", "after", "actor_user_id", "created_at"):
        assert key in e_inv

    c = client.post("/api/v1/customers", json={"name": "AuditDel", "email": "audit-del@example.com"})
    assert c.status_code == 200
    cid = c.json()["id"]
    r_del = client.delete(f"/api/v1/customers/{cid}", headers=headers)
    assert r_del.status_code == 200
    e_cust = _find_latest_audit(action="DELETE", entity="Customer")
    for key in ("before", "after", "actor_user_id", "created_at"):
        assert key in e_cust

    r_set = client.patch(
        "/api/v1/settings/services/pricing",
        json={"value": "flat-rate"},
        headers=headers,
    )
    assert r_set.status_code == 200
    e_set = _find_latest_audit(action="PATCH", entity="settings")
    for key in ("before", "after", "actor_user_id", "created_at"):
        assert key in e_set

    client.patch("/api/v1/settings/services/pricing", json={"value": "variable"}, headers=headers)
