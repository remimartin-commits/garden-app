from __future__ import annotations

import pytest

from app.entities import ServiceTemplate


class TestServiceTemplate:
    def test_valid_service_template(self) -> None:
        service = ServiceTemplate(
            name="Lawn Mowing",
            description="Standard lawn mowing service",
            base_price=30.0,
            gst_enabled=True,
            labels=["lawn", "mowing"],
        )
        assert service.name == "Lawn Mowing"
        assert service.base_price == 30.0

    def test_negative_base_price(self) -> None:
        with pytest.raises(ValueError, match="Base price cannot be negative"):
            ServiceTemplate(
                name="Garden Cleaning",
                description="Complete Garden Clean",
                base_price=-50.0,
                gst_enabled=True,
            )


def test_service_template_creation() -> None:
    template = ServiceTemplate(
        name="Garden Maintenance",
        description="Regular garden maintenance service",
        base_price=200.0,
        gst_enabled=True,
    )
    assert template.name == "Garden Maintenance"
    assert template.description == "Regular garden maintenance service"
    assert template.base_price == 200.0
    assert template.gst_enabled is True
    assert template.calculate_gst() == 30.0


def test_service_template_no_gst() -> None:
    template = ServiceTemplate(
        name="Lawn Mowing",
        description="Mow",
        base_price=100.0,
        gst_enabled=False,
    )
    assert template.calculate_gst() == 0.0
