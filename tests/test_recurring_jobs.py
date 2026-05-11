from __future__ import annotations

from datetime import datetime

import pytest
from app.schemas.recurring_job_rule import RecurringJobRule


def test_preview_recurring_jobs_api(client):
    response = client.post("/api/v1/recurring-job-rules/1/preview", json={})
    assert response.status_code == 200
    data = response.json()
    if isinstance(data, dict) and "jobs" in data:
        rows = data["jobs"]
    else:
        rows = data
    assert isinstance(rows, list)
    assert len(rows) >= 1
    first = rows[0]
    assert first["parent_recurring_rule_id"] == 1
    assert "generated_for_date" in first


def test_preview_recurring_jobs_schema():
    rule = RecurringJobRule(id=123)
    date = datetime(2023, 10, 5)
    preview = rule.preview_jobs(date)
    assert len(preview) == 1
    assert preview[0]["parent_recurring_rule_id"] == 123
    assert preview[0]["generated_for_date"] == date
