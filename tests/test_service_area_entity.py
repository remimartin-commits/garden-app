import pytest

from app.entities import ServiceArea


def test_service_area_entity_has_required_fields():
    area = ServiceArea(
        name="Auckland Pool Installation",
        slug="auckland-pool-installation",
        island="North Island",
        regions=["Auckland", "Northland", "Waikato"],
        description="Complete swimming pool design and installation services across the upper North Island.",
        key_locations=["Auckland", "Whangarei", "Hamilton"],
        coverage_notes="Nationwide installation team available for residential, developer, and commercial projects.",
        services_available=["consultation", "design", "excavation", "construction", "handover"],
        response_time="Quotes usually returned within two business days.",
    )

    assert area.name == "Auckland Pool Installation"
    assert area.slug == "auckland-pool-installation"
    assert area.island == "North Island"
    assert area.regions == ["Auckland", "Northland", "Waikato"]
    assert area.key_locations == ["Auckland", "Whangarei", "Hamilton"]
    assert area.active is True


def test_service_area_entity_serializes_for_site_content():
    area = ServiceArea(
        name="South Island Pool Installation",
        slug="south-island-pool-installation",
        island="South Island",
        regions=["Canterbury", "Otago", "Southland"],
        description="End-to-end pool installation coverage for South Island homeowners and commercial clients.",
    )

    payload = area.to_dict()

    assert payload["name"] == "South Island Pool Installation"
    assert payload["island"] == "South Island"
    assert payload["regions"] == ["Canterbury", "Otago", "Southland"]
    assert payload == area.model_dump()


def test_service_area_entity_requires_core_fields():
    with pytest.raises(ValueError, match="name is required"):
        ServiceArea(
            name="",
            slug="north-island",
            island="North Island",
            regions=["Auckland"],
            description="Coverage description.",
        )

    with pytest.raises(ValueError, match="regions must contain at least one item"):
        ServiceArea(
            name="North Island",
            slug="north-island",
            island="North Island",
            regions=[],
            description="Coverage description.",
        )


def test_service_area_entity_restricts_island_values():
    with pytest.raises(ValueError, match="island must be one of"):
        ServiceArea(
            name="Australian Pool Installation",
            slug="australia-pool-installation",
            island="Australia",
            regions=["Queensland"],
            description="Invalid coverage for a New Zealand nationwide pool installer.",
        )
