from __future__ import annotations

from app.auth import has_permission
from app.entities import Role, User


def test_gardener_job_permissions() -> None:
    gardener_role = Role(name="gardener", permissions=["jobs.read", "jobs.complete"])
    user = User(username="test_gardener", role=gardener_role)
    assert has_permission(user, "GET", "/api/v1/jobs/1") is True
    assert has_permission(user, "POST", "/api/v1/jobs/1/complete") is True
    assert has_permission(user, "POST", "/api/v1/invoices") is False
    assert has_permission(user, "PATCH", "/api/v1/settings/some_category/some_key") is False
