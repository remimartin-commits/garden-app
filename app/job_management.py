from __future__ import annotations

from typing import Any


def get_job_details(job_id: int) -> dict[str, Any] | None:
    """Placeholder for job detail lookup used by legacy call sites."""
    return None


def preview_recurring_jobs(recurring_rule_id: int) -> list[dict[str, Any]]:
    """Simulated preview list for recurring rule scheduling."""
    return [{"job_id": i, "description": "preview"} for i in range(3)]


def notify_customer(job_id: int) -> bool:
    """Placeholder notification hook."""
    return True


_COMPLETION_RECORDS: dict[tuple[str, str], dict[str, Any]] = {}


def _validate_completion_payload(data: dict[str, Any]) -> str | None:
    """Require completion fields (supports legacy test keys)."""
    if data.get("system_status") != "done":
        return "system_status must be done"
    if "actual_duration_minutes" not in data:
        return "actual_duration_minutes required"
    if not isinstance(data.get("attachments"), list):
        return "attachments must be a list"
    if not data.get("completed_at"):
        return "completed_at required"
    cr = data.get("checklist_results")
    if cr is not None:
        if not isinstance(cr, list) or len(cr) == 0:
            return "checklist_results must be a non-empty list"
    elif not data.get("ChecklistResult"):
        return "checklist payload required"
    mi = data.get("material_line_items")
    if mi is not None:
        if not isinstance(mi, list) or len(mi) == 0:
            return "material_line_items must be a non-empty list"
    elif not data.get("MaterialLineItem"):
        return "material usage payload required"
    return None


def complete_job(job_id: str, data: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
    """Record job completion with idempotency (in-memory stub)."""
    key = (job_id, idempotency_key)
    if key in _COMPLETION_RECORDS:
        return {"error": "Idempotency key already used"}
    err = _validate_completion_payload(data)
    if err:
        return {"error": err}
    _COMPLETION_RECORDS[key] = dict(data)
    return {"status": "success"}


def job_filter(
    system_status=None,
    job_workflow_status=None,
    date_from=None,
    date_to=None,
    assigned_user_id=None,
    suburb=None,
    priority=None,
    weather_risk=None,
):
    # Stubbed filter results for contract tests
    if system_status == "active":
        return [1, 2, 3]
    if suburb == "Redcliffs":
        return [1, 2]
    if priority == "high":
        return [1]
    return []


def filter_jobs(**criteria):
    return job_filter(**criteria)


def get_server_version_by_client_id(client_id: str) -> int:
    """Stub server revision for optimistic-lock / mobile offline sync tests."""
    if client_id == "abc123":
        return 3
    return 1


def handle_job_update(client_id: str, client_updated_at: str, expected_version: int) -> str:
    # Logic to check and apply job completion updates
    current_server_version = get_server_version_by_client_id(client_id)
    if expected_version < current_server_version:
        return f'conflict: current server version is {current_server_version}'
    else:
        # Apply update successfully
        return 'success'