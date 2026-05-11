from __future__ import annotations

from app.entities import BusinessProfile


def test_gst_rate_change_affects_new_items_only() -> None:
    initial_rate = 0.15
    new_rate = 0.10
    profile = BusinessProfile(
        name="Co",
        gst_number="1",
        address="addr",
        contact_email="a@b.co",
        phone_number="1",
        gst_rate=initial_rate,
    )
    profile.update_gst_rate(new_rate)
    assert profile.gst_rate == new_rate
