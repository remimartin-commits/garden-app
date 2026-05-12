from __future__ import annotations

import pytest

from tests.http_helpers import auth_test_client


@pytest.mark.skip(reason="Autonomy status route is not mounted on the garden manager app.")
def test_autonomy_status_route_registered() -> None:
    client = auth_test_client()
    response = client.get("/autonomy/status")
    assert response.status_code == 200


def test_read_recurring_job_rule_success() -> None:
    client = auth_test_client()
    response = client.get("/api/v1/recurring-job-rules/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert "cadence" in data


def test_read_recurring_job_rule_not_found() -> None:
    client = auth_test_client()
    response = client.get("/api/v1/recurring-job-rules/999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Recurring job rule not found"}
