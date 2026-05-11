from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_service_templates() -> None:
    response = client.get("/api/v1/service-templates")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 2
    statuses = {row["status"] for row in data}
    assert "active" in statuses
    assert "inactive" in statuses
    names = {row["name"] for row in data}
    assert "Lawn Mowing" in names
    assert "Hedge Trimming" in names


@pytest.mark.skip(reason="DELETE /api/v1/service-templates/{id} is not implemented (legacy Flask/SQLAlchemy test).")
def test_delete_service_template() -> None:
    """Reserved for template soft-delete when that endpoint exists."""
    raise AssertionError("unreachable when not skipped")
