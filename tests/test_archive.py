from __future__ import annotations

import pytest

from app.entities import BusinessProfile


def test_soft_archive():
    business_profile = BusinessProfile(
        name="Test Gardens Ltd",
        gst_number="12-345-678",
        address="1 Example Road",
        contact_email="owner@example.test",
        phone_number="0210000000",
    )
    business_profile.soft_archive()
    assert business_profile.archived_at is not None
