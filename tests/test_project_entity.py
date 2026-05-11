import pytest

from app.entities import Project


def test_project_captures_required_gallery_and_location_fields():
    project = Project(
        title="Queenstown family pool retreat",
        location="Queenstown",
        region="Otago",
        island="South Island",
        pool_type="Concrete in-ground pool",
        key_features=["Integrated spa", "Mountain-view glass fencing"],
        image_urls=["/images/projects/queenstown-family-pool.jpg"],
        description="A complete design and installation project for a residential pool.",
        client_type="homeowner",
        services_delivered=["Consultation", "Design", "Excavation", "Handover"],
        completion_year=2025,
    )

    data = project.to_dict()

    assert data["title"] == "Queenstown family pool retreat"
    assert data["location"] == "Queenstown"
    assert data["region"] == "Otago"
    assert data["island"] == "South Island"
    assert data["pool_type"] == "Concrete in-ground pool"
    assert data["key_features"] == ["Integrated spa", "Mountain-view glass fencing"]
    assert data["image_urls"] == ["/images/projects/queenstown-family-pool.jpg"]
    assert data["services_delivered"] == ["Consultation", "Design", "Excavation", "Handover"]
    assert data["completion_year"] == 2025
    assert data["status"] == "completed"


def test_project_requires_core_text_fields():
    with pytest.raises(ValueError, match="title"):
        Project(
            title=" ",
            location="Auckland",
            region="Auckland",
            island="North Island",
            pool_type="Fibreglass pool",
            key_features=["Low-maintenance finish"],
            image_urls=["/images/projects/auckland-pool.jpg"],
        )


def test_project_requires_key_features_and_images():
    with pytest.raises(ValueError, match="key_features"):
        Project(
            title="Auckland courtyard pool",
            location="Auckland",
            region="Auckland",
            island="North Island",
            pool_type="Fibreglass pool",
            key_features=[],
            image_urls=["/images/projects/auckland-pool.jpg"],
        )

    with pytest.raises(ValueError, match="image_urls"):
        Project(
            title="Auckland courtyard pool",
            location="Auckland",
            region="Auckland",
            island="North Island",
            pool_type="Fibreglass pool",
            key_features=["Compact urban installation"],
            image_urls=[],
        )


def test_project_validates_new_zealand_island_and_completion_year():
    with pytest.raises(ValueError, match="island"):
        Project(
            title="Commercial pool upgrade",
            location="Wellington",
            region="Wellington",
            island="Nationwide",
            pool_type="Commercial lap pool",
            key_features=["Lane markings", "Accessible entry"],
            image_urls=["/images/projects/wellington-commercial-pool.jpg"],
        )

    with pytest.raises(ValueError, match="completion_year"):
        Project(
            title="Commercial pool upgrade",
            location="Wellington",
            region="Wellington",
            island="North Island",
            pool_type="Commercial lap pool",
            key_features=["Lane markings", "Accessible entry"],
            image_urls=["/images/projects/wellington-commercial-pool.jpg"],
            completion_year=1800,
        )
