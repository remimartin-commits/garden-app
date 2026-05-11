import pytest

from app.entities import Page


VALID_PAGE_DATA = {
    "title": "Nationwide Swimming Pool Installation",
    "slug": "services/nationwide-swimming-pool-installation",
    "meta_description": "Complete swimming pool design and installation services across New Zealand.",
    "hero_heading": "Swimming pool installation anywhere in New Zealand",
    "hero_subheading": "From design and excavation to finishing and handover, our team manages the full pool build.",
    "sections": [
        {
            "heading": "Full-service pool builds",
            "content": "Consultation, design, excavation, construction, finishing, and client handover.",
        },
        {
            "heading": "Nationwide coverage",
            "content": "Serving homeowners, developers, and commercial clients across the North Island and South Island.",
        },
    ],
    "calls_to_action": [
        {"label": "Request a quote", "url": "/quote"},
        {"label": "View pool projects", "url": "/projects"},
    ],
}


def test_page_entity_contains_required_fields_and_round_trips():
    page = Page(**VALID_PAGE_DATA)

    assert page.title == "Nationwide Swimming Pool Installation"
    assert page.slug == "services/nationwide-swimming-pool-installation"
    assert page.hero_heading == "Swimming pool installation anywhere in New Zealand"
    assert page.sections[0]["heading"] == "Full-service pool builds"
    assert page.calls_to_action[0]["label"] == "Request a quote"
    assert page.to_dict() == VALID_PAGE_DATA
    assert Page.from_dict(page.to_dict()) == page


@pytest.mark.parametrize(
    "field_name, invalid_value",
    [
        ("title", ""),
        ("meta_description", "   "),
        ("hero_heading", None),
        ("hero_subheading", ""),
    ],
)
def test_page_entity_rejects_missing_required_text_fields(field_name, invalid_value):
    data = dict(VALID_PAGE_DATA)
    data[field_name] = invalid_value

    with pytest.raises(ValueError, match=field_name):
        Page(**data)


def test_page_entity_rejects_invalid_slug():
    data = dict(VALID_PAGE_DATA)
    data["slug"] = "Services/Nationwide Pool Installation"

    with pytest.raises(ValueError, match="slug"):
        Page(**data)


@pytest.mark.parametrize("field_name", ["sections", "calls_to_action"])
def test_page_entity_requires_non_empty_collections(field_name):
    data = dict(VALID_PAGE_DATA)
    data[field_name] = []

    with pytest.raises(ValueError, match=field_name):
        Page(**data)


def test_page_entity_requires_section_heading_and_content():
    data = dict(VALID_PAGE_DATA)
    data["sections"] = [{"heading": "Design", "content": ""}]

    with pytest.raises(ValueError, match="sections\[0\].content"):
        Page(**data)


def test_page_entity_requires_call_to_action_label_and_url():
    data = dict(VALID_PAGE_DATA)
    data["calls_to_action"] = [{"label": "Request a quote", "url": ""}]

    with pytest.raises(ValueError, match="calls_to_action\[0\].url"):
        Page(**data)


def test_page_entity_from_dict_reports_missing_fields():
    data = dict(VALID_PAGE_DATA)
    data.pop("hero_heading")

    with pytest.raises(ValueError, match="missing required page fields: hero_heading"):
        Page.from_dict(data)
