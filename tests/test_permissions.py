from __future__ import annotations

import pytest

from app.auth import has_permission


@pytest.fixture
def gardener_user() -> dict[str, object]:
    return {"role": "gardener", "permissions": {"jobs.read", "jobs.complete"}}


def test_gardener_can_read_jobs(gardener_user: dict[str, object]) -> None:
    assert has_permission(gardener_user, "jobs.read")


def test_gardener_can_complete_jobs(gardener_user: dict[str, object]) -> None:
    assert has_permission(gardener_user, "jobs.complete")


def test_gardener_cannot_post_invoices(gardener_user: dict[str, object]) -> None:
    assert not has_permission(gardener_user, "invoices.post")


def test_gardener_cannot_patch_settings(gardener_user: dict[str, object]) -> None:
    assert not has_permission(gardener_user, "settings.patch")
