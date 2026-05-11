import pytest

from app.entities import Service


def test_service_entity_captures_required_fields():
    service = Service(
        name="Complete Pool Installation",
        slug="complete-pool-installation",
        summary="End-to-end swimming pool installation anywhere in New Zealand.",
        description=(
            "A full-service installation package covering consultation, design, "
            "excavation, construction, finishing, and handover."
        ),
        process_steps=[
            "Consultation and site assessment",
            "Design and specification",
            "Excavation and construction",
            "Finishing and handover",
        ],
        features=[
            "Nationwide project delivery",
            "Residential and commercial pools",
            "Quote enquiry workflow",
        ],
    )

    assert service.name == "Complete Pool Installation"
    assert service.title == service.name
    assert service.slug == "complete-pool-installation"
    assert service.coverage == "Nationwide New Zealand"
    assert "Consultation and site assessment" in service.process_steps
    assert "Nationwide project delivery" in service.features
    assert "Homeowners" in service.target_clients


def test_service_entity_generates_slug_and_supports_content_aliases():
    service = Service(
        title="Concrete Swimming Pools",
        short_description="Custom concrete pool builds for New Zealand properties.",
        description="Design-led concrete pool installation for complex residential sites.",
        stages=["Design", "Excavation", "Construction"],
        inclusions=["Custom shape", "Premium finish"],
    )

    assert service.name == "Concrete Swimming Pools"
    assert service.slug == "concrete-swimming-pools"
    assert service.summary == "Custom concrete pool builds for New Zealand properties."
    assert service.process_steps == ["Design", "Excavation", "Construction"]
    assert service.features == ["Custom shape", "Premium finish"]


def test_service_entity_serializes_to_dict():
    service = Service(
        name="Fibreglass Pool Installation",
        summary="Fast, durable fibreglass pool installation nationwide.",
        description="A complete fibreglass pool installation service for Kiwi homes.",
        process_steps=["Measure", "Install", "Handover"],
        features=["Low maintenance", "Quick installation"],
        pool_type="fibreglass",
    )

    data = service.to_dict()

    assert data["slug"] == "fibreglass-pool-installation"
    assert data["pool_type"] == "fibreglass"
    assert data["installation_steps"] == ["Measure", "Install", "Handover"]
    assert Service.from_dict(data).to_dict() == data


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {
            "name": "Missing summary",
            "description": "Description exists.",
            "process_steps": ["Step"],
            "features": ["Feature"],
        },
        {
            "name": "Missing process",
            "summary": "Summary exists.",
            "description": "Description exists.",
            "features": ["Feature"],
        },
        {
            "name": "Missing features",
            "summary": "Summary exists.",
            "description": "Description exists.",
            "process_steps": ["Step"],
        },
    ],
)
def test_service_entity_requires_core_fields(kwargs):
    with pytest.raises(ValueError):
        Service(**kwargs)
